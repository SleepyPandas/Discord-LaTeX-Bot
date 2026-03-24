import base64
import csv
import hmac
import io
import logging
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from aiohttp import ClientSession, ClientTimeout, web


BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
ERROR_STATUSES = ("timeout", "compile_error", "internal_error", "rejected")
WINDOW_HOURS_BY_KEY = {
    "24h": 24,
    "7d": 7 * 24,
    "30d": 30 * 24,
    "90d": 90 * 24,
}
DEFAULT_WINDOW_KEY = "90d"
RUNTIME_CACHE_TTL_SECONDS = 300
LOGGER = logging.getLogger(__name__)


def get_metrics_db_path() -> str:
    """Resolve metrics database location from environment."""
    return os.getenv("METRICS_DB_PATH", "/data/metrics.db")


def get_dashboard_username() -> str:
    return os.getenv("DASHBOARD_USERNAME", "admin")


def get_dashboard_password() -> str:
    return os.getenv("DASHBOARD_PASSWORD", "change-me")


def get_app_version() -> str:
    return os.getenv("APP_VERSION") or os.getenv("IMAGE_VERSION", "unknown")


def get_build_date() -> str:
    return os.getenv("BUILD_DATE", "unknown")


def get_git_sha() -> str:
    return os.getenv("GIT_SHA", "unknown")


def get_dashboard_github_repo() -> str:
    return os.getenv("DASHBOARD_GITHUB_REPO", "SleepyPandas/Discord-LaTeX-Bot")


def get_dashboard_github_branch() -> str:
    return os.getenv("DASHBOARD_GITHUB_BRANCH", "main")


def get_github_token() -> str:
    return os.getenv("GITHUB_TOKEN", "")


def _format_uptime(seconds: int) -> str:
    total = max(0, int(seconds))
    days, remainder = divmod(total, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)
    if days > 0:
        return f"{days}d {hours}h {minutes}m"
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    if minutes > 0:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def _determine_update_status(running_sha: str, main_sha: str) -> str:
    run = (running_sha or "").strip().lower()
    latest = (main_sha or "").strip().lower()
    if not run or run == "unknown" or not latest:
        return "unknown"
    if run == latest or latest.startswith(run) or run.startswith(latest):
        return "up_to_date"
    return "update_available"


def _increment_restart_count(db_path: str, started_at_iso: str) -> int:
    db_file = Path(db_path)
    try:
        db_file.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        LOGGER.exception("Failed to create parent directory for db=%s", db_path)
        return 1

    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS dashboard_runtime_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )
            row = conn.execute(
                "SELECT value FROM dashboard_runtime_meta WHERE key = 'restart_count';"
            ).fetchone()
            current_count = 0
            if row and row[0] is not None:
                try:
                    current_count = int(row[0])
                except (TypeError, ValueError):
                    current_count = 0
            restart_count = current_count + 1
            conn.execute(
                """
                INSERT INTO dashboard_runtime_meta (key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value;
                """,
                ("restart_count", str(restart_count)),
            )
            conn.execute(
                """
                INSERT INTO dashboard_runtime_meta (key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value;
                """,
                ("last_started_at", started_at_iso),
            )
            conn.commit()
            return restart_count
    except sqlite3.Error:
        LOGGER.exception("Failed to update restart count in db=%s", db_path)
        return 1


async def _fetch_latest_main_sha(repo: str, branch: str, token: str) -> str:
    timeout = ClientTimeout(total=4)
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "latex-dashboard-monitor",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    url = f"https://api.github.com/repos/{repo}/commits/{branch}"
    async with ClientSession(timeout=timeout) as session:
        async with session.get(url, headers=headers) as response:
            if response.status != 200:
                body = await response.text()
                raise RuntimeError(f"github_status={response.status} body={body[:200]}")
            payload = await response.json()

    sha = str(payload.get("sha", "")).strip()
    if not sha:
        raise RuntimeError("missing sha in GitHub response")
    return sha


async def _runtime_update_status(app: web.Application) -> dict:
    now = datetime.now(timezone.utc)
    cache = app["runtime_update_cache"]
    checked_at = cache.get("checked_at")
    cached_payload = cache.get("payload")
    if checked_at and cached_payload:
        age_seconds = (now - checked_at).total_seconds()
        if age_seconds < RUNTIME_CACHE_TTL_SECONDS:
            return cached_payload

    running_sha = app["runtime_git_sha"]
    repo = app["runtime_github_repo"]
    branch = app["runtime_github_branch"]
    token = app["runtime_github_token"]

    main_sha = ""
    error = ""
    try:
        main_sha = await _fetch_latest_main_sha(repo, branch, token)
    except Exception as exc:
        error = str(exc)
        LOGGER.warning("Failed to fetch GitHub main SHA: %s", error)

    payload = {
        "github_repo": repo,
        "github_branch": branch,
        "main_sha": main_sha,
        "update_status": _determine_update_status(running_sha, main_sha),
        "checked_at": now.isoformat(timespec="seconds"),
        "error": error,
    }
    cache["checked_at"] = now
    cache["payload"] = payload
    return payload


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
        "queued": 0,
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
                "SELECT COUNT(*) FROM latex_events WHERE created_at >= ? AND status != 'queued';",
                (threshold,),
            )
            response["queued"] = _fetch_one_int(
                conn,
                "SELECT COUNT(*) FROM latex_events WHERE created_at >= ? AND status = 'queued';",
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
                WHERE created_at >= ? AND status IN (?, ?, ?, ?);
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
                bucket = by_source.setdefault(source, {"attempts": 0, "errors": 0, "successes": 0, "queued": 0})
                if status != "queued":
                    bucket["attempts"] += int(total)
                if status == "success":
                    bucket["successes"] += int(total)
                elif status in ERROR_STATUSES:
                    bucket["errors"] += int(total)
                elif status == "queued":
                    bucket["queued"] += int(total)
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
            "queued": [0] * bucket_count,
        },
        "errors_by_status": {
            "timeout": [0] * bucket_count,
            "compile_error": [0] * bucket_count,
            "internal_error": [0] * bucket_count,
            "rejected": [0] * bucket_count,
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

        status = row["status"]
        if status != "queued":
            response["totals"]["attempts"][index] += 1

        if status == "success":
            response["totals"]["successes"][index] += 1
        elif status in ERROR_STATUSES:
            response["totals"]["errors"][index] += 1
            response["errors_by_status"][status][index] += 1
        elif status == "queued":
            response["totals"]["queued"][index] += 1

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


def _query_all_events(db_path: str) -> list[dict]:
    if not Path(db_path).exists():
        return []

    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT id, created_at, source, status, dpi, user_id, error_message
                FROM latex_events
                ORDER BY id DESC;
                """
            ).fetchall()
    except sqlite3.Error:
        LOGGER.exception("Failed to query all events from db=%s", db_path)
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


def _events_to_csv(events: list[dict]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["id", "created_at", "source", "status", "dpi", "user_id", "error_message"])
    for event in events:
        writer.writerow(
            [
                event.get("id"),
                event.get("created_at"),
                event.get("source"),
                event.get("status"),
                event.get("dpi"),
                event.get("user_id"),
                event.get("error_message"),
            ]
        )
    return buffer.getvalue()


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


async def api_events_export(request: web.Request) -> web.Response:
    events = _query_all_events(request.app["metrics_db_path"])
    csv_payload = _events_to_csv(events)
    filename = f"latex-events-{datetime.now(timezone.utc).strftime('%Y%m%d')}.csv"
    return web.Response(
        text=csv_payload,
        content_type="text/csv",
        charset="utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


async def api_runtime(request: web.Request) -> web.Response:
    now = datetime.now(timezone.utc)
    started_at = request.app["runtime_started_at"]
    uptime_seconds = int((now - started_at).total_seconds())
    update_data = await _runtime_update_status(request.app)

    return web.json_response(
        {
            "uptime_seconds": max(0, uptime_seconds),
            "uptime_human": _format_uptime(uptime_seconds),
            "restart_count": request.app["runtime_restart_count"],
            "app_version": request.app["runtime_app_version"],
            "build_date": request.app["runtime_build_date"],
            "git_sha": request.app["runtime_git_sha"],
            "github_repo": update_data.get("github_repo", ""),
            "github_branch": update_data.get("github_branch", ""),
            "main_sha": update_data.get("main_sha", ""),
            "update_status": update_data.get("update_status", "unknown"),
            "update_checked_at": update_data.get("checked_at", ""),
            "update_error": update_data.get("error", ""),
            "generated_at": now.isoformat(timespec="seconds"),
        }
    )


def create_app() -> web.Application:
    app = web.Application(middlewares=[basic_auth_middleware])
    app["metrics_db_path"] = get_metrics_db_path()
    app["dashboard_username"] = get_dashboard_username()
    app["dashboard_password"] = get_dashboard_password()
    started_at = datetime.now(timezone.utc)
    app["runtime_started_at"] = started_at
    app["runtime_app_version"] = get_app_version()
    app["runtime_build_date"] = get_build_date()
    app["runtime_git_sha"] = get_git_sha()
    app["runtime_github_repo"] = get_dashboard_github_repo()
    app["runtime_github_branch"] = get_dashboard_github_branch()
    app["runtime_github_token"] = get_github_token()
    app["runtime_restart_count"] = _increment_restart_count(
        app["metrics_db_path"],
        started_at.isoformat(timespec="seconds"),
    )
    app["runtime_update_cache"] = {"checked_at": None, "payload": None}
    app.router.add_get("/", index)
    app.router.add_get("/healthz", health)
    app.router.add_get("/api/summary", api_summary)
    app.router.add_get("/api/timeseries", api_timeseries)
    app.router.add_get("/api/events", api_events)
    app.router.add_get("/api/events/export.csv", api_events_export)
    app.router.add_get("/api/runtime", api_runtime)
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
