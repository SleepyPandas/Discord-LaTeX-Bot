import logging
import os
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path


_VALID_STATUSES = {"success", "timeout", "compile_error", "internal_error"}
_DEFAULT_RETENTION_DAYS = 90
_DEFAULT_MAX_SIZE_BYTES = 512 * 1024 * 1024
_DEFAULT_MAINTENANCE_INTERVAL_SECONDS = 60
_PRUNE_BATCH_SIZE = 5000
_MIN_RETENTION_DAYS = 1
_MIN_MAX_SIZE_BYTES = 1024 * 1024
_MIN_MAINTENANCE_INTERVAL_SECONDS = 1
_LOGGER = logging.getLogger(__name__)
_MAINTENANCE_STATE_LOCK = threading.Lock()
_LAST_MAINTENANCE_RUN_MONOTONIC: dict[str, float] = {}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _utc_cutoff_iso(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")


def _read_positive_int_env(var_name: str, default_value: int, minimum: int) -> int:
    raw_value = os.getenv(var_name)
    if raw_value is None:
        return default_value
    try:
        parsed = int(raw_value)
    except (TypeError, ValueError):
        return default_value
    if parsed < minimum:
        return default_value
    return parsed


def _get_retention_days() -> int:
    return _read_positive_int_env(
        "METRICS_RETENTION_DAYS",
        _DEFAULT_RETENTION_DAYS,
        _MIN_RETENTION_DAYS,
    )


def _get_max_size_bytes() -> int:
    return _read_positive_int_env(
        "METRICS_MAX_SIZE_BYTES",
        _DEFAULT_MAX_SIZE_BYTES,
        _MIN_MAX_SIZE_BYTES,
    )


def _get_maintenance_interval_seconds() -> int:
    return _read_positive_int_env(
        "METRICS_MAINTENANCE_INTERVAL_SECONDS",
        _DEFAULT_MAINTENANCE_INTERVAL_SECONDS,
        _MIN_MAINTENANCE_INTERVAL_SECONDS,
    )


def _metrics_storage_size_bytes(db_path: str) -> int:
    paths = (Path(db_path), Path(f"{db_path}-wal"), Path(f"{db_path}-shm"))
    total = 0
    for path in paths:
        try:
            total += path.stat().st_size
        except FileNotFoundError:
            continue
    return total


def _delete_oldest_batch(conn: sqlite3.Connection, batch_size: int) -> int:
    cursor = conn.execute(
        """
        DELETE FROM latex_events
        WHERE id IN (
            SELECT id
            FROM latex_events
            ORDER BY created_at ASC, id ASC
            LIMIT ?
        );
        """,
        (batch_size,),
    )
    return int(cursor.rowcount or 0)


def _run_metrics_maintenance(db_path: str) -> None:
    retention_days = _get_retention_days()
    max_size_bytes = _get_max_size_bytes()
    retention_cutoff = _utc_cutoff_iso(retention_days)

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "DELETE FROM latex_events WHERE created_at < ?;",
            (retention_cutoff,),
        )
        conn.commit()

        current_size = _metrics_storage_size_bytes(db_path)
        if current_size <= max_size_bytes:
            return

        while current_size > max_size_bytes:
            deleted_rows = _delete_oldest_batch(conn, _PRUNE_BATCH_SIZE)
            conn.commit()

            conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
            conn.execute("VACUUM;")
            current_size = _metrics_storage_size_bytes(db_path)

            if deleted_rows <= 0:
                break


def _should_run_throttled_maintenance(db_path: str) -> bool:
    interval_seconds = _get_maintenance_interval_seconds()
    db_key = str(Path(db_path))
    now_monotonic = time.monotonic()

    with _MAINTENANCE_STATE_LOCK:
        previous = _LAST_MAINTENANCE_RUN_MONOTONIC.get(db_key)
        if previous is not None and (now_monotonic - previous) < interval_seconds:
            return False
        _LAST_MAINTENANCE_RUN_MONOTONIC[db_key] = now_monotonic
        return True


def init_metrics_db(db_path: str) -> None:
    path = Path(db_path)
    if path.parent and str(path.parent) not in ("", "."):
        path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS latex_events (
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
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_latex_events_created_at ON latex_events(created_at);"
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_latex_events_created_at_status
            ON latex_events(created_at, status);
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_latex_events_created_at_source
            ON latex_events(created_at, source);
            """
        )
        conn.commit()

    try:
        _run_metrics_maintenance(str(path))
    except sqlite3.Error:
        _LOGGER.exception("Metrics maintenance failed during db init path=%s", path)


def record_latex_event(
    db_path: str,
    source: str,
    status: str,
    dpi: int | None,
    user_id: int | None,
    error_message: str | None = None,
) -> None:
    if status not in _VALID_STATUSES:
        raise ValueError(f"Invalid status '{status}'")

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO latex_events (created_at, source, status, dpi, user_id, error_message)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            (
                _utc_now_iso(),
                source,
                status,
                dpi,
                str(user_id) if user_id is not None else None,
                (error_message or "")[:500] or None,
            ),
        )
        conn.commit()

    if not _should_run_throttled_maintenance(db_path):
        return

    try:
        _run_metrics_maintenance(db_path)
    except sqlite3.Error:
        _LOGGER.exception("Metrics maintenance failed during event write path=%s", db_path)
