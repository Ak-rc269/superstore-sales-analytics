"""Offline regression checks for the supplied Superstore dataset.

Run from the project directory:
    python -m unittest discover -s tests -v

Only pandas and the local modules are used; no database or Google API calls
are made. SUPERSTORE_TEST_CSV can select another copy of the same source CSV.
The baseline values were independently calculated from the uploaded file.
"""

from datetime import date
from decimal import Decimal
import json
import os
from pathlib import Path
import sys
import unittest

import pandas as pd

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from ingest import read_source
from publish import dataframe_to_values, write_worksheet
from transform import transform_dataframe


class DatasetRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = Path(os.environ.get(
            "SUPERSTORE_TEST_CSV", str(PROJECT_DIR / "data/raw/superstore.csv")
        ))
        cls.raw = read_source(source)
        cls.tables, cls.quality = transform_dataframe(cls.raw)
        cls.detail = cls.tables["sales_detail"]

    def test_source_counts_and_independent_financial_baseline(self):
        self.assertEqual(self.raw.shape, (9994, 21))
        self.assertEqual(self.raw.attrs["source_encoding"], "cp1252")
        self.assertEqual(len(self.detail), 9994)
        self.assertEqual(self.detail["order_id"].nunique(), 5009)
        self.assertEqual(self.detail["customer_id"].nunique(), 793)
        # Decimal also verifies that source parsing did not alter original values.
        expected_sales = Decimal("2297200.8603")
        expected_profit = Decimal("286397.0217")
        self.assertEqual(sum(map(Decimal, self.raw["sales"])), expected_sales)
        self.assertEqual(sum(map(Decimal, self.raw["profit"])), expected_profit)
        self.assertAlmostEqual(self.detail["sales"].sum(), float(expected_sales), places=6)
        self.assertAlmostEqual(self.detail["profit"].sum(), float(expected_profit), places=6)
        self.assertEqual(self.detail["quantity"].sum(), 37873)
        self.assertAlmostEqual(
            self.quality["profit_margin"], float(expected_profit / expected_sales), places=12
        )

    def test_losses_and_suspected_business_duplicates_are_retained(self):
        self.assertEqual((self.detail["profit"] < 0).sum(), 1871)
        self.assertEqual(self.detail["is_loss"].sum(), 1871)
        self.assertEqual(self.quality["rows_dropped"], 0)
        self.assertEqual(self.quality["exact_duplicate_rows"], 0)
        self.assertEqual(self.quality["duplicate_business_rows_excluding_row_id"], 1)
        self.assertEqual(set(self.quality["possible_duplicate_row_ids"]), {"3406", "3407"})
        pair = self.detail[self.detail["row_id"].isin(["3406", "3407"])]
        self.assertEqual(len(pair), 2)
        self.assertAlmostEqual(pair["sales"].sum(), 562.744, places=6)
        self.assertAlmostEqual(pair["profit"].sum(), -24.1176, places=6)

    def test_all_summary_totals_reconcile_without_adding_distinct_counts(self):
        expected_rows = {
            "monthly_summary": 48, "subcategory_summary": 17,
            "region_summary": 4, "segment_summary": 3, "discount_summary": 4,
        }
        for name, rows in expected_rows.items():
            with self.subTest(table=name):
                summary = self.tables[name]
                self.assertEqual(len(summary), rows)
                self.assertAlmostEqual(summary["sales"].sum(), 2297200.8603, places=6)
                self.assertAlmostEqual(summary["profit"].sum(), 286397.0217, places=6)
                self.assertEqual(summary["quantity"].sum(), 37873)
                self.assertEqual(summary["line_count"].sum(), 9994)
        # The same order may contain multiple subcategories or discount bands.
        # Their distinct counts must remain per-group, not be forced to add up.
        self.assertEqual(self.tables["monthly_summary"]["order_count"].sum(), 5009)
        self.assertGreater(self.tables["subcategory_summary"]["order_count"].sum(), 5009)
        chairs = self.tables["subcategory_summary"].set_index("sub_category").loc["Chairs"]
        self.assertEqual(chairs["order_count"], 576)
        self.assertEqual(chairs["line_count"], 617)
        self.assertAlmostEqual(chairs["profit_margin"], 0.08095673289143, places=12)

    def test_dates_are_us_format_and_postal_codes_remain_text(self):
        first = self.detail.set_index("row_id").loc["1"]
        self.assertEqual(first["order_date"], pd.Timestamp("2016-11-08"))
        self.assertEqual(first["ship_date"], pd.Timestamp("2016-11-11"))
        self.assertEqual(first["shipping_days"], 3)
        self.assertEqual(first["order_month"], pd.Timestamp("2016-11-01"))
        self.assertEqual(self.detail["order_date"].min(), pd.Timestamp("2014-01-03"))
        self.assertEqual(self.detail["order_date"].max(), pd.Timestamp("2017-12-30"))
        self.assertTrue(self.detail["postal_code"].str.fullmatch(r"\d{5}").all())
        self.assertEqual(self.detail["postal_code"].str.startswith("0").sum(), 449)
        self.assertEqual(self.quality["us_postal_codes_padded"], 438)
        self.assertEqual(self.raw["postal_code"].str.startswith("0").sum(), 11)

    def test_text_cleanup_and_repeatability_do_not_mutate_raw_data(self):
        before = self.raw.copy(deep=True)
        second_tables, second_quality = transform_dataframe(self.raw)
        pd.testing.assert_frame_equal(self.raw, before)
        for name in self.tables:
            pd.testing.assert_frame_equal(self.tables[name], second_tables[name])
        self.assertEqual(self.quality, second_quality)
        self.assertEqual(self.quality["product_name_nbsp_cells_original"], 225)
        self.assertFalse(self.detail["product_name"].str.contains("\u00a0", regex=False).any())
        self.assertTrue(self.detail["product_name"].eq(self.detail["product_name"].str.strip()).all())

    def test_discount_boundaries(self):
        sample = self.raw.iloc[:6].copy()
        sample["discount"] = ["0", "0.01", "0.2", "0.2001", "0.4", "0.4001"]
        tables, _ = transform_dataframe(sample)
        self.assertEqual(tables["sales_detail"]["discount_band"].tolist(), [
            "0%", "(0%, 20%]", "(0%, 20%]", "(20%, 40%]", "(20%, 40%]", ">40%"
        ])

    def test_invalid_required_values_and_duplicate_ids_are_rejected(self):
        cases = [
            ("order_date", "31/12/2017"), ("ship_date", "not-a-date"),
            ("sales", "invalid"), ("profit", "inf"), ("discount", "1.1"),
            ("quantity", "1.5"), ("order_id", " "),
        ]
        for column, value in cases:
            with self.subTest(column=column, value=value):
                sample = self.raw.iloc[:2].copy()
                sample.loc[sample.index[0], column] = value
                with self.assertRaises(ValueError):
                    transform_dataframe(sample)
        sample = self.raw.iloc[:2].copy()
        sample.loc[sample.index[1], "row_id"] = " 1 "
        with self.assertRaisesRegex(ValueError, "row_id is not unique"):
            transform_dataframe(sample)


class RecordingWorksheet:
    """Minimal observable stand-in for Google Sheets, with an optional failure."""
    def __init__(self, rows=100, cols=40, fail_update=None):
        self.row_count = rows
        self.col_count = cols
        self.events = []
        self.fail_update = fail_update
        self.update_count = 0

    def resize(self, *, rows, cols):
        self.events.append(("resize", rows, cols))
        self.row_count, self.col_count = rows, cols

    def update(self, **kwargs):
        self.update_count += 1
        self.events.append(("update", kwargs))
        if self.update_count == self.fail_update:
            raise RuntimeError("Simulated network failure")

    def batch_format(self, formats):
        self.events.append(("format", formats))

    def freeze(self, **kwargs):
        self.events.append(("freeze", kwargs))


class PublicationRegressionTests(unittest.TestCase):
    def test_values_are_json_safe_and_dates_have_verified_serial_anchors(self):
        frame = pd.DataFrame({
            "order_date": [date(1899, 12, 30), "1970-01-01", pd.Timestamp("2000-01-01")],
            "observed_at": [pd.Timestamp("2000-01-01 12:00"), pd.NaT, pd.Timestamp("1970-01-01")],
            "sales": [Decimal("281.3720"), 12.5, 0],
            "profit": [Decimal("-12.0588"), float("nan"), pd.NA],
            "postal_code": ["05401", "00123", "02110"],
            "product_name": ["=literal", "+literal", "ordinary"],
        })
        values = dataframe_to_values(frame)
        json.dumps(values, allow_nan=False)
        self.assertEqual([row[0] for row in values[1:]], [0.0, 25569.0, 36526.0])
        self.assertEqual([row[1] for row in values[1:]], [36526.5, "", 25569.0])
        self.assertEqual(values[1][2:6], [281.372, -12.0588, "05401", "=literal"])
        self.assertEqual(values[2][3], "")
        self.assertEqual(values[3][3], "")

    def test_raw_updates_keep_literal_strings_and_shrink_only_after_writes(self):
        frame = pd.DataFrame({
            "order_date": [date(2000, 1, 1), date(2000, 1, 2), date(2000, 1, 3)],
            "sales": [1.5, 2.5, 3.5], "product_name": ["=literal", "item", "other"],
        })
        worksheet = RecordingWorksheet(rows=100, cols=40)
        write_worksheet(worksheet, frame, chunk_rows=2)
        self.assertEqual(worksheet.events[0], ("resize", 100, 40))
        updates = [event[1] for event in worksheet.events if event[0] == "update"]
        self.assertEqual([item["range_name"] for item in updates], ["A1:C2", "A3:C4"])
        self.assertTrue(all(item["value_input_option"] == "RAW" for item in updates))
        self.assertEqual(updates[0]["values"][1][2], "=literal")
        self.assertEqual(worksheet.events[3], ("resize", 4, 3))
        self.assertEqual((worksheet.row_count, worksheet.col_count), (4, 3))
        formats = next(event[1] for event in worksheet.events if event[0] == "format")
        date_format = next(item for item in formats if item["range"] == "A2:A4")
        self.assertEqual(date_format["format"]["numberFormat"]["type"], "DATE")

    def test_failed_update_does_not_shrink_existing_sheet(self):
        worksheet = RecordingWorksheet(rows=100, cols=40, fail_update=2)
        frame = pd.DataFrame({"sales": [1, 2, 3]})
        with self.assertRaisesRegex(RuntimeError, "Simulated"):
            write_worksheet(worksheet, frame, chunk_rows=2)
        self.assertEqual((worksheet.row_count, worksheet.col_count), (100, 40))
        self.assertEqual([event[0] for event in worksheet.events], ["resize", "update", "update"])

    def test_nonfinite_numbers_and_timezone_dates_are_rejected(self):
        for frame in [
            pd.DataFrame({"sales": [float("inf")]}),
            pd.DataFrame({"order_date": [pd.Timestamp("2020-01-01", tz="UTC")]}),
        ]:
            with self.subTest(columns=frame.columns.tolist()):
                with self.assertRaises(ValueError):
                    dataframe_to_values(frame)


if __name__ == "__main__":
    unittest.main()
