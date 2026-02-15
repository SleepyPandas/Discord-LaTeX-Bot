import os
from pathlib import Path

from aiohttp import web


BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"


def get_metrics_db_path() -> str:
    """Resolve metrics database location from environment."""
    return os.getenv("METRICS_DB_PATH", "/data/metrics.db")


async def index(_: web.Request) -> web.FileResponse:
    return web.FileResponse(TEMPLATES_DIR / "index.html")


async def health(_: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


def create_app() -> web.Application:
    app = web.Application()
    app["metrics_db_path"] = get_metrics_db_path()
    app.router.add_get("/", index)
    app.router.add_get("/healthz", health)
    app.router.add_static("/static", STATIC_DIR)
    return app


if __name__ == "__main__":
    host = os.getenv("DASHBOARD_HOST", "0.0.0.0")
    port = int(os.getenv("DASHBOARD_PORT", "8081"))
    web.run_app(create_app(), host=host, port=port)
