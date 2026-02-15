import sqlite3
from datetime import datetime, timezone
from pathlib import Path


_VALID_STATUSES = {"success", "timeout", "compile_error", "internal_error"}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


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
        conn.commit()


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
