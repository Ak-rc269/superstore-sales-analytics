"""Clean raw PostgreSQL rows and build the six production analysis tables."""

import json
import logging
import math
from pathlib import Path

import pandas as pd

from config import Settings, get_engine, get_settings
from ingest import SOURCE_COLUMNS

LOG = logging.getLogger(__name__)
DISCOUNT_BANDS = ["0%", "(0%, 20%]", "(20%, 40%]", ">40%"]
DATE_COLUMNS = {"order_date", "ship_date", "order_month"}


def _fail_if(frame: pd.DataFrame, mask: pd.Series, message: str) -> None:
    if mask.fillna(True).any():
        examples = frame.loc[mask.fillna(True), "row_id"].astype(str).head(5).tolist()
        raise ValueError(f"{message} Example row_id values: {', '.join(examples)}")


def _summary(frame: pd.DataFrame, dimensions: list[str]) -> pd.DataFrame:
    result = frame.groupby(dimensions, dropna=False, observed=True).agg(
        sales=("sales", "sum"), profit=("profit", "sum"),
        quantity=("quantity", "sum"), order_count=("order_id", "nunique"),
        line_count=("row_id", "size"),
    ).reset_index()
    # Weighted overall margin, never the average of row-level percentage margins.
    result["profit_margin"] = result["profit"].div(result["sales"].where(result["sales"].ne(0)))
    return result.sort_values(dimensions, kind="stable").reset_index(drop=True)


def transform_dataframe(raw: pd.DataFrame) -> tuple[dict[str, pd.DataFrame], dict]:
    """Pure transformation, usable for offline verification without PostgreSQL.

    The source is order-line data. A repeated order_id or a matching business
    row with a different row_id is not automatically removed. Invalid required
    dates/numbers/IDs stop the run instead of silently changing the totals.
    """
    missing = sorted(set(SOURCE_COLUMNS) - set(raw.columns))
    if missing:
        raise ValueError(f"Missing raw columns: {', '.join(missing)}")
    if raw.empty:
        raise ValueError("raw_data.superstore is empty. Run ingest.py first.")
    frame = raw.loc[:, SOURCE_COLUMNS].copy()
    quality = {
        "input_rows": int(len(frame)),
        "input_columns": int(len(frame.columns)),
        "exact_duplicate_rows": int(frame.duplicated().sum()),
        "duplicate_business_rows_excluding_row_id": int(frame.drop(columns="row_id").duplicated().sum()),
        "possible_duplicate_row_ids": frame.loc[
            frame.drop(columns="row_id").duplicated(keep=False), "row_id"
        ].astype(str).tolist(),
        "product_name_nbsp_cells_original": int(
            frame["product_name"].astype("string").str.contains("\u00a0", regex=False, na=False).sum()
        ),
        "missing_before": {},
        "text_normalized_cells": {},
        "missing_category_values_filled": {},
        "rows_dropped": 0,
        "grain": "One order line identified by row_id; order_id is not unique.",
    }
    for column in frame.columns:
        values = frame[column].astype("string")
        cleaned = values.str.replace("\u00a0", " ", regex=False).str.strip()
        changed = values.fillna("").ne(cleaned.fillna(""))
        quality["text_normalized_cells"][column] = int(changed.sum())
        frame[column] = cleaned.mask(cleaned.eq(""), pd.NA)
        quality["missing_before"][column] = int(frame[column].isna().sum())
    quality["product_names_normalized_total"] = quality["text_normalized_cells"]["product_name"]

    for column in ("row_id", "order_id", "customer_id", "product_id"):
        _fail_if(frame, frame[column].isna(), f"Required ID {column} is missing.")
    _fail_if(frame, frame["row_id"].duplicated(keep=False), "row_id is not unique after normalization.")

    for column in ("order_date", "ship_date"):
        converted = pd.to_datetime(frame[column], format="%m/%d/%Y", errors="coerce")
        _fail_if(frame, converted.isna(), f"{column} must be a valid US-format MM/DD/YYYY date.")
        frame[column] = converted

    for column in ("sales", "quantity", "discount", "profit"):
        converted = pd.to_numeric(frame[column], errors="coerce")
        invalid = converted.isna() | ~converted.map(lambda value: math.isfinite(value) if pd.notna(value) else False)
        _fail_if(frame, invalid, f"{column} must be a finite number.")
        frame[column] = converted.astype("float64")
    _fail_if(frame, frame["sales"].lt(0), "sales must not be negative in this sales-only dataset.")
    _fail_if(frame, frame["quantity"].le(0) | frame["quantity"].mod(1).ne(0), "quantity must be a positive integer.")
    _fail_if(frame, ~frame["discount"].between(0, 1), "discount must be a fraction between 0 and 1.")
    frame["quantity"] = frame["quantity"].astype("int64")

    for column in ("ship_mode", "segment", "country", "city", "state", "region", "category", "sub_category"):
        count = int(frame[column].isna().sum())
        if count:
            frame[column] = frame[column].fillna("Unknown")
            quality["missing_category_values_filled"][column] = count

    # Keep postal codes as text. Restore the five-digit US ZIP representation.
    us_zip = frame["country"].eq("United States") & frame["postal_code"].str.fullmatch(r"\d{1,5}", na=False)
    postal_before = frame["postal_code"].copy()
    frame.loc[us_zip, "postal_code"] = frame.loc[us_zip, "postal_code"].str.zfill(5)
    quality["us_postal_codes_padded"] = int(postal_before.fillna("").ne(frame["postal_code"].fillna("")).sum())

    frame["order_year"] = frame["order_date"].dt.year
    frame["order_month"] = frame["order_date"].dt.to_period("M").dt.to_timestamp()
    frame["year_month"] = frame["order_date"].dt.strftime("%Y-%m")
    frame["shipping_days"] = (frame["ship_date"] - frame["order_date"]).dt.days
    _fail_if(frame, frame["shipping_days"].lt(0), "ship_date is before order_date.")
    frame["discount_band"] = ">40%"
    frame.loc[frame["discount"].le(0.4), "discount_band"] = "(20%, 40%]"
    frame.loc[frame["discount"].le(0.2), "discount_band"] = "(0%, 20%]"
    frame.loc[frame["discount"].eq(0), "discount_band"] = "0%"
    frame["discount_band_sort"] = frame["discount_band"].map({label: index for index, label in enumerate(DISCOUNT_BANDS)})
    frame["is_loss"] = frame["profit"].lt(0).astype("int64")

    tables = {
        "sales_detail": frame,
        "monthly_summary": _summary(frame, ["order_month", "year_month"]),
        "subcategory_summary": _summary(frame, ["category", "sub_category"]),
        "region_summary": _summary(frame, ["region"]),
        "segment_summary": _summary(frame, ["segment"]),
        "discount_summary": _summary(frame, ["discount_band_sort", "discount_band"]),
    }
    total_sales = float(frame["sales"].sum())
    total_profit = float(frame["profit"].sum())
    quality.update({
        "output_rows": int(len(frame)),
        "output_columns": int(len(frame.columns)),
        "orders": int(frame["order_id"].nunique()),
        "customers": int(frame["customer_id"].nunique()),
        "sales": total_sales,
        "profit": total_profit,
        "profit_margin": total_profit / total_sales if total_sales else None,
        "loss_lines_retained": int(frame["is_loss"].sum()),
        "first_order_date": frame["order_date"].min().strftime("%Y-%m-%d"),
        "last_order_date": frame["order_date"].max().strftime("%Y-%m-%d"),
        "discount_band_definitions": {"0%": "discount = 0", "(0%, 20%]": "0 < discount <= 0.2", "(20%, 40%]": "0.2 < discount <= 0.4", ">40%": "0.4 < discount <= 1"},
        "summary_rows": {name: int(len(table)) for name, table in tables.items()},
        "notes": [
            "No rows are removed automatically. Matching lines with different row_id values are retained.",
            "Negative profit is a valid business result and is retained.",
            "Shipping days measures order-to-ship time, not delivery-to-customer time.",
            "Group order_count values are not additive when an order appears in more than one group.",
            "profit_margin is SUM(profit) / SUM(sales); a zero denominator produces a missing ratio.",
        ],
    })
    # The original object is never modified; raw database values remain untouched.
    return tables, quality


def export_tables(tables: dict[str, pd.DataFrame], quality: dict, output_dir: str | Path) -> None:
    """Write inspectable UTF-8 CSVs and machine-readable validation results."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, frame in tables.items():
        frame.to_csv(output_dir / f"{name}.csv", index=False, encoding="utf-8-sig", date_format="%Y-%m-%d")
    (output_dir / "data_quality.json").write_text(
        json.dumps(quality, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _sql_types(frame: pd.DataFrame) -> dict:
    from sqlalchemy import BigInteger, Date, Numeric, Text
    result = {}
    for column in frame.columns:
        if column in DATE_COLUMNS:
            result[column] = Date()
        elif pd.api.types.is_integer_dtype(frame[column]):
            result[column] = BigInteger()
        elif pd.api.types.is_numeric_dtype(frame[column]):
            result[column] = Numeric(24, 8)
        else:
            result[column] = Text()
    return result


def transform(settings: Settings | None = None) -> tuple[dict[str, pd.DataFrame], dict]:
    """Read raw_data from PostgreSQL, transform, then atomically replace production tables."""
    settings = settings or get_settings()
    engine = get_engine(settings)
    from sqlalchemy import text
    from sqlalchemy.exc import SQLAlchemyError

    try:
        with engine.connect() as connection:
            raw = pd.read_sql_query(text('SELECT * FROM "raw_data"."superstore" ORDER BY "row_id"'), connection)
        tables, quality = transform_dataframe(raw)
        with engine.begin() as connection:
            connection.execute(text('CREATE SCHEMA IF NOT EXISTS "production"'))
            for name, frame in tables.items():
                frame.to_sql(
                    name, connection, schema="production", if_exists="replace",
                    index=False, dtype=_sql_types(frame), chunksize=1000, method="multi",
                )
            connection.execute(text('ALTER TABLE "production"."sales_detail" ADD PRIMARY KEY ("row_id")'))
    except SQLAlchemyError:
        raise RuntimeError(
            "Transformation could not read or write PostgreSQL. Check that Docker is "
            "healthy, .env matches its database settings, and ingest.py has completed."
        ) from None
    finally:
        engine.dispose()
    export_tables(tables, quality, settings.output_dir)
    LOG.info("Created %s production tables from %s order lines.", len(tables), quality["output_rows"])
    LOG.info("Data-quality report and CSV exports: %s", settings.output_dir)
    return tables, quality


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        transform()
    except Exception as error:
        LOG.error("Transformation failed: %s", error)
        raise SystemExit(1)
