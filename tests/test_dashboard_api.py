import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "monitoring" / "dashboard"))

import app as dashboard_app


def _iso_hours_ago(hours_ago: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat(timespec="seconds")


class DashboardApiTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = str(Path(self.temp_dir.name) / "metrics.db")
        self._create_schema()

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except PermissionError:
            pass

    def _create_schema(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE latex_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    source TEXT NOT NULL,
                    status TEXT NOT NULL,
                    dpi INTEGER,
                    user_id TEXT,
                    error_message TEXT
                );
                """
            )
            conn.commit()

    def _insert_rows(self, rows: list[tuple]) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.executemany(
                """
                INSERT INTO latex_events (created_at, source, status, dpi, user_id, error_message)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                rows,
            )
            conn.commit()

    def test_parse_window_key_defaults_to_90d_for_invalid_or_missing(self):
        self.assertEqual(dashboard_app._parse_window_key(None), "90d")
        self.assertEqual(dashboard_app._parse_window_key("invalid"), "90d")
        self.assertEqual(dashboard_app._parse_window_key("7d"), "7d")

    def test_query_summary_counts_by_window(self):
        rows = [
            (_iso_hours_ago(2), "slash", "success", 275, "1", None),
            (_iso_hours_ago(3), "slash", "compile_error", 275, "1", "bad latex"),
            (_iso_hours_ago(30), "legacy", "success", 275, "2", None),
            (_iso_hours_ago(24 * 8), "legacy", "timeout", 275, "3", "timed out"),
            (_iso_hours_ago(24 * 45), "slash", "internal_error", 275, "4", "boom"),
            (_iso_hours_ago(24 * 95), "slash", "success", 275, "5", None),
        ]
        self._insert_rows(rows)

        expected = {
            "24h": (2, 1, 1),
            "7d": (3, 2, 1),
            "30d": (4, 2, 2),
            "90d": (5, 2, 3),
        }

        for window_key, counts in expected.items():
            with self.subTest(window_key=window_key):
                summary = dashboard_app._query_summary(self.db_path, window_key)
                self.assertEqual(summary["window"]["key"], window_key)
                self.assertEqual(summary["attempts"], counts[0])
                self.assertEqual(summary["successes"], counts[1])
                self.assertEqual(summary["errors"], counts[2])

    def test_timeseries_returns_aligned_series_lengths(self):
        rows = [
            (_iso_hours_ago(1), "slash", "success", 275, "1", None),
            (_iso_hours_ago(2), "slash", "compile_error", 275, "2", "bad latex"),
            (_iso_hours_ago(25), "legacy", "timeout", 275, "3", "timed out"),
            (_iso_hours_ago(24 * 26), "legacy", "internal_error", 275, "4", "boom"),
        ]
        self._insert_rows(rows)

        for window_key in ("24h", "7d", "30d", "90d"):
            with self.subTest(window_key=window_key):
                data = dashboard_app._query_timeseries(self.db_path, window_key)
                bucket_count = data["window"]["bucket_count"]
                self.assertEqual(len(data["labels"]), bucket_count)
                self.assertEqual(len(data["totals"]["attempts"]), bucket_count)
                self.assertEqual(len(data["totals"]["successes"]), bucket_count)
                self.assertEqual(len(data["totals"]["errors"]), bucket_count)
                self.assertEqual(len(data["errors_by_status"]["timeout"]), bucket_count)
                self.assertEqual(len(data["errors_by_status"]["compile_error"]), bucket_count)
                self.assertEqual(len(data["errors_by_status"]["internal_error"]), bucket_count)
                for values in data["by_source"].values():
                    self.assertEqual(len(values), bucket_count)

    def test_timeseries_empty_db_is_zero_filled(self):
        missing_db_path = str(Path(self.temp_dir.name) / "missing.db")
        data = dashboard_app._query_timeseries(missing_db_path, "90d")

        self.assertEqual(data["window"]["key"], "90d")
        self.assertEqual(data["window"]["bucket_count"], 90)
        self.assertEqual(len(data["labels"]), 90)
        self.assertEqual(sum(data["totals"]["attempts"]), 0)
        self.assertEqual(sum(data["totals"]["successes"]), 0)
        self.assertEqual(sum(data["totals"]["errors"]), 0)
        self.assertEqual(data["by_source"], {})


if __name__ == "__main__":
    unittest.main()
