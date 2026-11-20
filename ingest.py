"""Load the original Superstore CSV into raw_data.superstore as text."""

import logging
from pathlib import Path
import re

import pandas as pd

from config import Settings, get_engine, get_settings

LOG = logging.getLogger(__name__)
SOURCE_COLUMNS = (
    "row_id", "order_id", "order_date", "ship_date", "ship_mode", "customer_id",
    "customer_name", "segment", "country", "city", "state", "postal_code",
    "region", "product_id", "category", "sub_category", "product_name",
    "sales", "quantity", "discount", "profit",
)


def read_source(path: str | Path) -> pd.DataFrame:
    """Preserve cell values, including leading zeros, before transformation.

    The supplied CSV is Windows-1252. UTF-8 exports are supported as well.
    Empty cells stay empty strings in raw_data rather than being invented values.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"CSV not found: {path}. Check CSV_PATH in .env.")
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            frame = pd.read_csv(path, encoding=encoding, dtype=str, keep_default_na=False)
            break
        except UnicodeDecodeError:
            if encoding == "cp1252":
                raise
    frame.columns = [
        re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")
        for name in frame.columns
    ]
    if frame.columns.duplicated().any():
        raise ValueError("CSV headers become duplicates after normalization.")
    missing = sorted(set(SOURCE_COLUMNS) - set(frame.columns))
    if missing:
        raise ValueError(f"Required CSV columns are missing: {', '.join(missing)}")
    if frame.empty:
        raise ValueError("CSV has no data rows.")
    # A row is an order line. Repeated order_id values are expected and retained.
    if frame["row_id"].str.strip().eq("").any() or frame["row_id"].duplicated().any():
        raise ValueError("row_id must be non-empty and unique. Resolve duplicate source row IDs.")
    frame.attrs["source_encoding"] = encoding
    return frame


def ingest(settings: Settings | None = None) -> int:
    settings = settings or get_settings()
    frame = read_source(settings.csv_path)
    engine = get_engine(settings)
    from sqlalchemy import Text, text

    try:
        # PostgreSQL DDL and inserts commit together. Reruns replace only our table.
        with engine.begin() as connection:
            connection.execute(text('CREATE SCHEMA IF NOT EXISTS "raw_data"'))
            frame.to_sql(
                "superstore", connection, schema="raw_data", if_exists="replace",
                index=False, dtype={column: Text() for column in frame.columns},
                chunksize=1000, method="multi",
            )
            connection.execute(text(
                'ALTER TABLE "raw_data"."superstore" ADD PRIMARY KEY ("row_id")'
            ))
    except Exception:
        raise RuntimeError(
            "Ingestion failed while writing PostgreSQL. Check docker compose ps, "
            "the database settings in .env, and the database user's permissions."
        ) from None
    finally:
        engine.dispose()
    LOG.info("Loaded %s rows (%s) into raw_data.superstore.", len(frame), frame.attrs["source_encoding"])
    return len(frame)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        ingest()
    except Exception as error:
        LOG.error("%s", error)
        raise SystemExit(1)
