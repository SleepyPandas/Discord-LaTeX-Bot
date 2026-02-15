import base64
import hmac
import logging
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from aiohttp import web


BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
ERROR_STATUSES = ("timeout", "compile_error", "internal_error")
WINDOW_HOURS_BY_KEY = {
    "24h": 24,
    "7d": 7 * 24,
    "30d": 30 * 24,
    "90d": 90 * 24,
}
DEFAULT_WINDOW_KEY = "90d"
LOGGER = logging.getLogger(__name__)


def get_metrics_db_path() -> str:
    """Resolve metrics database location from environment."""
    return os.getenv("METRICS_DB_PATH", "/data/metrics.db")


def get_dashboard_username() -> str:
    return os.getenv("DASHBOARD_USERNAME", "admin")


def get_dashboard_password() -> str:
    return os.getenv("DASHBOARD_PASSWORD", "change-me")


def _window_start_iso(hours: int = 24) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat(timespec="seconds")


def _parse_window_key(raw_value: str | None) -> str:
    if raw_value is None:
        return DEFAULT_WINDOW_KEY
    candidate = raw_value.strip().lower()
    if candidate in WINDOW_HOURS_BY_KEY:
        return candidate
    return DEFAULT_WINDOW_KEY


def _fetch_one_int(conn: sqlite3.Connection, query: str, params: tuple) -> int:
    cursor = conn.execute(query, params)
    row = cursor.fetchone()
    if row is None:
        return 0
    value = row[0]
    return int(value or 0)


def _query_summary(db_path: str, window_key: str) -> dict:
    window_hours = WINDOW_HOURS_BY_KEY[window_key]
    threshold = _window_start_iso(window_hours)
    response = {
        "window": {
            "key": window_key,
            "hours": window_hours,
            "start_utc": threshold,
        },
        "attempts": 0,
        "successes": 0,
        "errors": 0,
        "error_rate_percent": 0.0,
        "by_source": {},
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

    if not Path(db_path).exists():
        return response

    try:
        with sqlite3.connect(db_path) as conn:
            response["attempts"] = _fetch_one_int(
                conn,
                "SELECT COUNT(*) FROM latex_events WHERE created_at >= ?;",
                (threshold,),
            )
            response["successes"] = _fetch_one_int(
                conn,
                "SELECT COUNT(*) FROM latex_events WHERE created_at >= ? AND status = ?;",
                (threshold, "success"),
            )
            response["errors"] = _fetch_one_int(
                conn,
                """
                SELECT COUNT(*) FROM latex_events
                WHERE created_at >= ? AND status IN (?, ?, ?);
                """,
                (threshold, *ERROR_STATUSES),
            )

            by_source: dict[str, dict[str, int]] = {}
            rows = conn.execute(
                """
                SELECT source, status, COUNT(*) AS total
                FROM latex_events
                WHERE created_at >= ?
                GROUP BY source, status;
                """,
                (threshold,),
            ).fetchall()
            for source, status, total in rows:
                bucket = by_source.setdefault(source, {"attempts": 0, "errors": 0, "successes": 0})
                bucket["attempts"] += int(total)
                if status == "success":
                    bucket["successes"] += int(total)
                if status in ERROR_STATUSES:
                    bucket["errors"] += int(total)
            response["by_source"] = by_source
    except sqlite3.Error:
        LOGGER.exception("Failed to query summary from db=%s", db_path)
        return response

    attempts = response["attempts"]
    errors = response["errors"]
    if attempts > 0:
        response["error_rate_percent"] = round((errors / attempts) * 100.0, 2)
    return response


def _bucket_spec(window_key: str) -> tuple[str, int]:
    if window_key in {"24h", "7d"}:
        return "hour", WINDOW_HOURS_BY_KEY[window_key]
    return "day", WINDOW_HOURS_BY_KEY[window_key] // 24


def _bucket_step(bucket: str) -> timedelta:
    return timedelta(hours=1) if bucket == "hour" else timedelta(days=1)


def _floor_to_bucket(ts: datetime, bucket: str) -> datetime:
    if bucket == "hour":
        return ts.replace(minute=0, second=0, microsecond=0)
    return ts.replace(hour=0, minute=0, second=0, microsecond=0)


def _parse_event_timestamp(created_at: str) -> datetime | None:
    candidate = created_at.strip()
    if candidate.endswith("Z"):
        candidate = f"{candidate[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _query_timeseries(db_path: str, window_key: str) -> dict:
    window_hours = WINDOW_HOURS_BY_KEY[window_key]
    bucket, bucket_count = _bucket_spec(window_key)
    step = _bucket_step(bucket)
    now_utc = datetime.now(timezone.utc)
    end_bucket_start = _floor_to_bucket(now_utc, bucket)
    start_bucket = end_bucket_start - step * (bucket_count - 1)
    labels = [
        (start_bucket + step * index).isoformat(timespec="seconds")
        for index in range(bucket_count)
    ]
    response = {
        "window": {
            "key": window_key,
            "hours": window_hours,
            "bucket": bucket,
            "bucket_count": bucket_count,
            "start_utc": labels[0],
            "end_utc": labels[-1],
        },
        "labels": labels,
        "totals": {
            "attempts": [0] * bucket_count,
            "successes": [0] * bucket_count,
            "errors": [0] * bucket_count,
        },
        "errors_by_status": {
            "timeout": [0] * bucket_count,
            "compile_error": [0] * bucket_count,
            "internal_error": [0] * bucket_count,
        },
        "by_source": {},
        "generated_at": now_utc.isoformat(timespec="seconds"),
    }

    if not Path(db_path).exists():
        return response

    start_iso = labels[0]

    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT created_at, source, status
                FROM latex_events
                WHERE created_at >= ?
                ORDER BY created_at ASC;
                """,
                (start_iso,),
            ).fetchall()
    except sqlite3.Error:
        LOGGER.exception("Failed to query timeseries from db=%s", db_path)
        return response

    for row in rows:
        parsed = _parse_event_timestamp(row["created_at"])
        if parsed is None:
            continue
        bucket_start = _floor_to_bucket(parsed, bucket)
        if bucket_start < start_bucket or bucket_start > end_bucket_start:
            continue
        index = int((bucket_start - start_bucket) / step)
        if index < 0 or index >= bucket_count:
            continue

        response["totals"]["attempts"][index] += 1
        status = row["status"]
        if status == "success":
            response["totals"]["successes"][index] += 1
        elif status in ERROR_STATUSES:
            response["totals"]["errors"][index] += 1
            response["errors_by_status"][status][index] += 1

        source = row["source"]
        source_series = response["by_source"].setdefault(source, [0] * bucket_count)
        source_series[index] += 1

    return response


def _query_events(db_path: str, limit: int) -> list[dict]:
    if not Path(db_path).exists():
        return []

    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT id, created_at, source, status, dpi, user_id, error_message
                FROM latex_events
                ORDER BY id DESC
                LIMIT ?;
                """,
                (limit,),
            ).fetchall()
    except sqlite3.Error:
        LOGGER.exception("Failed to query events from db=%s", db_path)
        return []

    events = []
    for row in rows:
        events.append(
            {
                "id": row["id"],
                "created_at": row["created_at"],
                "source": row["source"],
                "status": row["status"],
                "dpi": row["dpi"],
                "user_id": row["user_id"],
                "error_message": row["error_message"],
            }
        )
    return events


def _unauthorized() -> web.Response:
    return web.Response(
        status=401,
        text="Authentication required",
        headers={"WWW-Authenticate": 'Basic realm="LaTeX Dashboard"'},
    )


def _is_authorized(request: web.Request) -> bool:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Basic "):
        return False

    encoded = auth_header.split(" ", maxsplit=1)[1].strip()
    try:
        decoded = base64.b64decode(encoded).decode("utf-8")
    except Exception:
        return False

    if ":" not in decoded:
        return False

    username, password = decoded.split(":", maxsplit=1)
    expected_user = request.app["dashboard_username"]
    expected_pass = request.app["dashboard_password"]
    return hmac.compare_digest(username, expected_user) and hmac.compare_digest(password, expected_pass)


@web.middleware
async def basic_auth_middleware(request: web.Request, handler):
    if request.path == "/healthz":
        return await handler(request)
    if not _is_authorized(request):
        return _unauthorized()
    return await handler(request)


async def index(_: web.Request) -> web.FileResponse:
    return web.FileResponse(TEMPLATES_DIR / "index.html")


async def health(_: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


async def api_summary(request: web.Request) -> web.Response:
    window_key = _parse_window_key(request.query.get("range"))
    summary = _query_summary(request.app["metrics_db_path"], window_key)
    return web.json_response(summary)


async def api_timeseries(request: web.Request) -> web.Response:
    window_key = _parse_window_key(request.query.get("range"))
    timeseries = _query_timeseries(request.app["metrics_db_path"], window_key)
    return web.json_response(timeseries)


async def api_events(request: web.Request) -> web.Response:
    limit_raw = request.query.get("limit", "50")
    try:
        limit = int(limit_raw)
    except ValueError:
        limit = 50
    limit = max(1, min(limit, 200))
    events = _query_events(request.app["metrics_db_path"], limit)
    return web.json_response({"events": events, "limit": limit})


def create_app() -> web.Application:
    app = web.Application(middlewares=[basic_auth_middleware])
    app["metrics_db_path"] = get_metrics_db_path()
    app["dashboard_username"] = get_dashboard_username()
    app["dashboard_password"] = get_dashboard_password()
    app.router.add_get("/", index)
    app.router.add_get("/healthz", health)
    app.router.add_get("/api/summary", api_summary)
    app.router.add_get("/api/timeseries", api_timeseries)
    app.router.add_get("/api/events", api_events)
    app.router.add_static("/static", STATIC_DIR)
    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [dashboard] %(message)s")

    username = get_dashboard_username()
    password = get_dashboard_password()
    if username == "admin" and password == "change-me":
        LOGGER.warning("Using default dashboard credentials. Set DASHBOARD_USERNAME/PASSWORD.")

    host = os.getenv("DASHBOARD_HOST", "0.0.0.0")
    port = int(os.getenv("DASHBOARD_PORT", "8081"))
    web.run_app(create_app(), host=host, port=port)
