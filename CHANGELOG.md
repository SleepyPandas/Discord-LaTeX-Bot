# Changelog

All notable changes to this project are documented in this file.

## #1 [Dashboard and Usage Logging] - 2026-02-15

Release candidate for branch `Feature/Dashboard-and-Useage-logging` (`18` commits ahead of `main`).

### Highlights

- Added persistent LaTeX compile metrics collection to the bot.
- Added a local monitoring dashboard service with charts, filtering, and recent event views.
- Added metrics retention and storage-size maintenance controls for long-running deployments.
- Added dashboard authentication and dockerized runtime support.
- Added automated tests for metrics storage and dashboard APIs.

### Added

- `src/metrics_store.py`
- `monitoring/dashboard/app.py`
- `monitoring/dashboard/templates/index.html`
- `monitoring/dashboard/static/style.css`
- `monitoring/dashboard/static/vendor/chart.umd.min.js` (local Chart.js bundle)
- `monitoring/dashboard/Dockerfile`
- `monitoring/dashboard/requirements.txt`
- `monitoring/data/.gitkeep`
- `tests/test_metrics_store.py`
- `tests/test_dashboard_api.py`

### Changed

- `src/bot.py`
- `docker-compose.yml`
- `README.md`
- `src/.env.example`
- `.gitignore`

### User-Facing Changes

- Dashboard now supports selectable windows: `24h`, `7d`, `30d`, `90d`.
- Dashboard includes summary cards, by-source breakdown, request/error trend charts, and latest compile events.
- Recent compile event timestamps are now displayed in Toronto/New York local time using:
  `YYYY MM DD - HH:MM:SS` (no timezone suffix).

### Operational Changes

- New dashboard service in compose stack, exposed on port `8081`.
- Bot and dashboard now share a single metrics database path (`/data/metrics.db` in compose).
- New dashboard HTTP Basic Auth environment variables:
  `DASHBOARD_USERNAME`, `DASHBOARD_PASSWORD`.

### Metrics and Data Policy

- Metrics recorded for both slash and legacy LaTeX command paths.
- Event statuses tracked: `success`, `timeout`, `compile_error`, `internal_error`.
- Retention and storage controls added:
  `METRICS_RETENTION_DAYS`, `METRICS_MAX_SIZE_BYTES`, `METRICS_MAINTENANCE_INTERVAL_SECONDS`.
- Maintenance prunes old rows and trims oldest data if the DB exceeds configured size.

