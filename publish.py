"""Publish production.sales_detail to one existing Google spreadsheet.

The destination worksheet belongs to this project. Its contents are refreshed
in place so its sheet ID, used by the Data Studio connector, remains stable.
"""

from __future__ import annotations

import json
import logging
import math
import numbers
import re
from datetime import date, datetime
from decimal import Decimal

import pandas as pd

from config import get_engine, get_settings

LOGGER = logging.getLogger(__name__)
SHEETS_EPOCH = pd.Timestamp("1899-12-30")
DATE_COLUMNS = {"order_date", "ship_date", "order_month"}


def column_letter(position: int) -> str:
    """Convert a positive, one-based column number into an A1 column name."""
    if position < 1:
        raise ValueError("Column numbers start at 1.")
    result = ""
    while position:
        position, remainder = divmod(position - 1, 26)
        result = chr(65 + remainder) + result
    return result


def spreadsheet_id(value: str) -> str:
    """Accept either a spreadsheet ID or its normal Google Sheets URL."""
    value = value.strip()
    match = re.search(r"/spreadsheets/d/([A-Za-z0-9_-]+)", value)
    if match:
        value = match.group(1)
    if not value or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError("Set GOOGLE_SHEET_ID in .env to your spreadsheet ID or URL.")
    return value


def validate_publish_config(settings=None) -> str:
    """Validate local prerequisites without connecting to Google."""
    settings = settings or get_settings()
    target_id = spreadsheet_id(settings.google_sheet_id)
    path = settings.google_credentials_path
    if not path.is_file():
        raise FileNotFoundError(
            "Google service-account JSON is missing. Save it as credentials.json "
            "or set GOOGLE_APPLICATION_CREDENTIALS. See README.md, Google setup."
        )
    try:
        credentials = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise ValueError("The Google credentials file is not valid JSON.") from exc
    if not isinstance(credentials, dict) or credentials.get("type") != "service_account" or not all(
        credentials.get(key) for key in ("client_email", "private_key", "token_uri")
    ):
        raise ValueError("Use a Google service-account JSON key, not an OAuth client file.")
    if not settings.google_worksheet_name.strip():
        raise ValueError("GOOGLE_WORKSHEET_NAME must not be empty.")
    return target_id


def _cell_value(value, column: str):
    if value is None or pd.isna(value):
        return ""
    if column in DATE_COLUMNS or isinstance(value, (pd.Timestamp, datetime, date)):
        stamp = pd.Timestamp(value)
        if stamp.tzinfo is not None:
            raise ValueError("Timezone-aware dates must be normalized before publication.")
        return float((stamp - SHEETS_EPOCH) / pd.Timedelta(days=1))
    if isinstance(value, bool):
        return value
    if isinstance(value, numbers.Integral):
        return int(value)
    if isinstance(value, (numbers.Real, Decimal)):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError(f"Non-finite number found in {column}.")
        return number
    # RAW input mode keeps text IDs, leading zeros and '=' prefixes literal.
    return str(value)


def dataframe_to_values(frame: pd.DataFrame) -> list[list]:
    """Return JSON-safe values, preserving numbers and spreadsheet date types."""
    columns = list(frame.columns)
    if not columns or frame.empty:
        raise ValueError("No production rows to publish. Run ingest and transform first.")
    return [columns] + [
        [_cell_value(value, column) for column, value in zip(columns, row)]
        for row in frame.itertuples(index=False, name=None)
    ]


def write_worksheet(worksheet, frame: pd.DataFrame, chunk_rows: int = 1000) -> None:
    """Update only the configured worksheet; retain its identity for BI refreshes."""
    if chunk_rows < 1:
        raise ValueError("chunk_rows must be positive.")
    values = dataframe_to_values(frame)
    needed_rows, needed_cols = len(values), len(values[0])
    # Expand first if needed. Shrink stale rows/columns only after successful writes.
    worksheet.resize(
        rows=max(worksheet.row_count, needed_rows),
        cols=max(worksheet.col_count, needed_cols),
    )
    end_column = column_letter(needed_cols)
    for start in range(0, needed_rows, chunk_rows):
        chunk = values[start:start + chunk_rows]
        worksheet.update(
            values=chunk,
            range_name=f"A{start + 1}:{end_column}{start + len(chunk)}",
            value_input_option="RAW",
        )
    worksheet.resize(rows=needed_rows, cols=needed_cols)
    formats = [{
        "range": f"A1:{end_column}1",
        "format": {
            "backgroundColor": {"red": 0.08, "green": 0.16, "blue": 0.24},
            "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
        },
    }]
    for index, column in enumerate(frame.columns, start=1):
        number_format = None
        if column in DATE_COLUMNS:
            number_format = {"type": "DATE", "pattern": "yyyy-mm-dd"}
        elif column in {"sales", "profit"}:
            number_format = {"type": "NUMBER", "pattern": "#,##0.00"}
        elif column in {"discount", "profit_margin"}:
            number_format = {"type": "PERCENT", "pattern": "0.00%"}
        elif column in {"quantity", "order_year", "shipping_days", "discount_band_sort", "is_loss"}:
            number_format = {"type": "NUMBER", "pattern": "0"}
        if number_format:
            letter = column_letter(index)
            formats.append({"range": f"{letter}2:{letter}{needed_rows}",
                            "format": {"numberFormat": number_format}})
    worksheet.batch_format(formats)
    worksheet.freeze(rows=1)


def publish(settings=None) -> str:
    """Read the database's final table and publish it to Google Sheets."""
    settings = settings or get_settings()
    target_id = validate_publish_config(settings)
    # Keep network/database dependencies lazy for local data verification.
    import gspread
    from sqlalchemy import text

    engine = get_engine(settings)
    try:
        with engine.connect() as connection:
            frame = pd.read_sql_query(
                text("SELECT * FROM production.sales_detail ORDER BY row_id"), connection
            )
    finally:
        engine.dispose()
    if frame.empty:
        raise ValueError("production.sales_detail has no rows.")
    client = gspread.service_account(filename=str(settings.google_credentials_path))
    try:
        spreadsheet = client.open_by_key(target_id)
    except gspread.SpreadsheetNotFound as exc:
        raise PermissionError(
            "Spreadsheet not found or not shared. Check GOOGLE_SHEET_ID and share "
            "the spreadsheet with the service account's client_email as Editor."
        ) from exc
    try:
        worksheet = spreadsheet.worksheet(settings.google_worksheet_name)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(
            title=settings.google_worksheet_name,
            rows=len(frame) + 1,
            cols=len(frame.columns),
        )
    write_worksheet(worksheet, frame)
    url = f"https://docs.google.com/spreadsheets/d/{target_id}/edit#gid={worksheet.id}"
    LOGGER.info("Published %s rows and %s columns to worksheet %s.",
                len(frame), len(frame.columns), settings.google_worksheet_name)
    LOGGER.info("Google Sheets: %s", url)
    return url


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        publish()
    except Exception as exc:
        # No credentials, connection strings or private keys are logged.
        LOGGER.error("Publish failed (%s). Check README.md troubleshooting.", type(exc).__name__)
        raise SystemExit(1)
