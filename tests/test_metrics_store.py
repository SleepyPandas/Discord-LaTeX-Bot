import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import metrics_store


def _iso_hours_ago(hours_ago: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat(timespec="seconds")


def _iso_days_ago(days_ago: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat(timespec="seconds")


class MetricsStoreTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = str(Path(self.temp_dir.name) / "metrics.db")
        metrics_store._LAST_MAINTENANCE_RUN_MONOTONIC.clear()

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except PermissionError:
            pass
        metrics_store._LAST_MAINTENANCE_RUN_MONOTONIC.clear()

    def _insert_event_row(self, created_at: str, source: str, status: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO latex_events (created_at, source, status, dpi, user_id, error_message)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (created_at, source, status, 275, "42", None),
            )
            conn.commit()

    def test_retention_prunes_rows_older_than_90_days(self):
        metrics_store.init_metrics_db(self.db_path)
        self._insert_event_row(_iso_days_ago(120), "legacy", "compile_error")
        self._insert_event_row(_iso_days_ago(2), "slash", "success")

        with patch.dict(
            os.environ,
            {
                "METRICS_RETENTION_DAYS": "90",
                "METRICS_MAX_SIZE_BYTES": str(512 * 1024 * 1024),
            },
            clear=False,
        ):
            metrics_store._run_metrics_maintenance(self.db_path)

        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("SELECT source, status FROM latex_events ORDER BY id ASC;").fetchall()

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], "slash")
        self.assertEqual(rows[0][1], "success")

    def test_size_cap_prunes_oldest_rows_first(self):
        metrics_store.init_metrics_db(self.db_path)
        oldest = _iso_hours_ago(10)
        middle = _iso_hours_ago(5)
        newest = _iso_hours_ago(1)
        self._insert_event_row(oldest, "legacy", "timeout")
        self._insert_event_row(middle, "slash", "compile_error")
        self._insert_event_row(newest, "slash", "success")

        with (
            patch.object(metrics_store, "_get_retention_days", return_value=3650),
            patch.object(metrics_store, "_get_max_size_bytes", return_value=500),
            patch.object(metrics_store, "_PRUNE_BATCH_SIZE", 1),
            patch.object(
                metrics_store,
                "_metrics_storage_size_bytes",
                side_effect=[1000, 1000, 400],
            ),
        ):
            metrics_store._run_metrics_maintenance(self.db_path)

        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT created_at, source, status FROM latex_events ORDER BY created_at ASC, id ASC;"
            ).fetchall()

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], newest)
        self.assertEqual(rows[0][2], "success")

    def test_invalid_env_values_fall_back_to_defaults(self):
        with patch.dict(
            os.environ,
            {
                "METRICS_RETENTION_DAYS": "not-a-number",
                "METRICS_MAX_SIZE_BYTES": "-1",
                "METRICS_MAINTENANCE_INTERVAL_SECONDS": "0",
            },
            clear=False,
        ):
            self.assertEqual(metrics_store._get_retention_days(), metrics_store._DEFAULT_RETENTION_DAYS)
            self.assertEqual(metrics_store._get_max_size_bytes(), metrics_store._DEFAULT_MAX_SIZE_BYTES)
            self.assertEqual(
                metrics_store._get_maintenance_interval_seconds(),
                metrics_store._DEFAULT_MAINTENANCE_INTERVAL_SECONDS,
            )

    def test_init_creates_database_and_records_event(self):
        metrics_store.init_metrics_db(self.db_path)
        metrics_store.record_latex_event(
            db_path=self.db_path,
            source="slash",
            status="success",
            dpi=275,
            user_id=1001,
            error_message=None,
        )

        with sqlite3.connect(self.db_path) as conn:
            count = conn.execute("SELECT COUNT(*) FROM latex_events;").fetchone()[0]

        self.assertTrue(Path(self.db_path).exists())
        self.assertEqual(count, 1)


if __name__ == "__main__":
    unittest.main()
