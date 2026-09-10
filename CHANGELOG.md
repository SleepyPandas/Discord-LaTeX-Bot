# Changelog

All notable changes to this project are documented in this file.

## [V2.5.2] [Varwidth Option for Standalone Document Normalization] - 2026-09-10

### Highlights

- Enabled the `varwidth` option on non-TikZ standalone documents (`\documentclass[varwidth,border=1mm]{standalone}`) when document environments (`\begin{document}...\end{document}`) are provided.
- Fixed TeX compilation failures on full documents that combine regular paragraph text with standalone display math blocks (`\[...\]` or equation environments).

### Added

- Regression test in `tests/test_latex_module.py` (`test_text_to_latex_renders_document_with_display_math_and_text`) verifying document rendering with mixed paragraph text and display math blocks.

### Changed

- `src/bot.py`: Bumped `__version__` to `2.5.2`.
- `src/latex_module.py`: Applied `[varwidth,border=1mm]` documentclass options in `_documentclass_options_for_content` when content does not require TikZ.

---

## [V2.5.1] [Fix Delimiter False Positives & Fallback Transparency] - 2026-09-09

### Highlights

- Fixed a false-positive preflight syntax error where LaTeX newline commands with spacing arguments (`\\[<length>]`) were incorrectly parsed as unclosed `\[` display math blocks.
- Fixed an issue where expressions falling back to `pdflatex` / `Latex2PNG` (e.g. inputs containing `\renewcommand`) rendered as opaque white rectangles due to missing format hints for Poppler transparency.

### Added

- Regression test in `tests/test_latex_module.py` ensuring newlines with optional spacing (`\\[4pt]`) and parenthesized expressions (`\\(a)`) pass preflight validation.
- Unit test in `tests/test_latex_compiler.py` verifying that `Latex2PNG` requests PNG format and transparency from `pdf2image`.

### Changed

- `src/bot.py`: Bumped `__version__` to `2.5.1`.
- `src/latex_module.py`: Updated `_detect_math_delimiter_issue` to skip escaped newlines (`\\`) before checking for math delimiters.
- `src/modified_packages/tex2img.py`: Explicitly passed `fmt='png'` to `pdf2image.convert_from_bytes` in `Latex2PNG.compile`.
- `src/modified_packages/pdf2image.py`: Automatically promoted default `fmt="ppm"` to `"png"` when `transparent=True` is requested.

---

## [V2.5.0] [Accurate Error Attribution & Display Math Support] - 2026-09-07

### Highlights

- Supported top-level AMS display math environments (`align*`, `gather*`, `multline*`, `alignat*`, etc.) without inline math delimiter conflicts.
- Fixed undefined command attribution to extract the actual failing macro from TeX error logs instead of the first command on the source line.
- Added visual source line snippets (`> line | content`) to multi-line compilation error messages.

### Added

- `_TOP_LEVEL_DISPLAY_MATH_ENV_RE` in `src/latex_module.py` detecting standalone display math environments.
- `_format_source_snippet` in `src/latex_module.py` providing line preview snippets for multi-line error embeds.
- `_find_user_line_for_command` in `src/latex_module.py` to pinpoint exact macro error lines in buffered blocks.
- Automated regression tests for display math rendering, nested command attribution, and multi-line error snippets.

### Changed

- `src/bot.py`: Bumped `__version__` to `2.5.0`.
- `src/latex_module.py`: Prevented wrapping top-level display math in inline delimiters, applied conditional `varwidth` to `standalone`, and prioritized TeX error logs (`<argument>`, snippet breakpoints) for undefined command extraction.

---

## [V2.4.2] [Help Command Version Display & Links] - 2026-09-06

### Highlights

- Added interactive link buttons directly to the `/help` command embed, providing quick navigation to Releases & Changelog, Feedback & Requests, and the GitHub repository.
- Added dynamic bot version display in the `/help` embed footer (`v2.4.2 • Created by SleepyPandas`).
- Added automated test coverage for `/help` command components and view buttons.

### Added

- `__version__` constant in `src/bot.py`.
- Discord UI `View` with link buttons attached to `/help` response.
- Automated tests verifying `/help` embed footer and button components in `tests/test_bot_modal_flow.py`.

### Changed

- `src/bot.py`: Updated `/help` slash command to display current version in the embed footer and attach interactive link buttons.

---

## [Additional Internal Error Logging & Error UX] - 2026-09-05

### Highlights

- Added database recording of failing LaTeX code specifically when compilation fails, times out, or encounters internal errors.
- Enhanced monitoring dashboard to inspect, review, and filter failing LaTeX snippets with dedicated UI styling and an error details modal.
- Added automatic fallback to local `monitoring/data/metrics.db` when running outside Docker without explicit environment variables.

### Added

- `latex_code` column in `latex_events` database schema (populated only on error conditions).
- Error details modal and LaTeX snippet viewing components in the dashboard UI.

### Changed

- `src/bot.py`: Passes `latex_code` to metrics recorder on `compile_error`, `timeout`, and `internal_error`.
- `src/metrics_store.py`: Added `latex_code` column support and automatic schema migration.
- `monitoring/dashboard/app.py`: Extracts `latex_code` in `/api/events` and falls back to repository metrics DB path during local development.
- `monitoring/dashboard/templates/index.html`: Added UI modal and view buttons for error code inspection.
- `monitoring/dashboard/static/style.css`: Added styling for error preview cards, modal dialogues, and monospaced code blocks.

---

## [Dashboard and Usage Logging] - 2026-02-15

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

---

## [V2.3.1] [Better Stack Heartbeat and Status Monitoring] - 2026-08-16

Release covering Pull Requests #60, #61, and #63.

### Highlights

- Added Better Stack periodic heartbeat background task to monitor bot uptime and detect outages.
- Added lightweight aiohttp health check server listening on port `8082` (`/healthz`).
- Added service status badge and Better Stack link to `README.md`.
- Added port mapping for health server (`8082:8082`) in Docker Compose configurations.
- Fixed SSL connection issues during heartbeat requests.
- Added test coverage for heartbeat dispatch and health endpoint responses.

### Added

- Better Stack heartbeat loop (`betterstack_heartbeat_task`) in `src/bot.py`
- Embedded HTTP health-check server (`/healthz`) on port `8082`
- Automated test cases in `tests/test_bot_modal_flow.py` verifying heartbeat dispatch and status reporting

### Changed

- `src/bot.py`: Integrated health server startup and heartbeat lifecycle tasks.
- `docker-compose.yml` & `docker-compose.prod.yml`: Exposed port `8082`.
- `README.md`: Added live status badge.

---

## [V2.2.1] [Drop Legacy Commands and Privileged Intents] - 2026-06-05

Release covering Pull Request #59.

### Highlights

- Dropped legacy message prefix command handling (`!latex`) in favor of Discord slash commands (`/latex`, `/quicklatex`, `/help`).
- Removed requirement for privileged Message Content Intent in the Discord Developer Portal.
- Simplified bot intent configuration to standard `discord.Intents.default()`.

### Changed

- `src/bot.py`: Removed `on_message` prefix command parser and privileged intent requirements.
- `src/latex_module.py`: Cleaned up legacy prefix command dependencies.
- `README.md`: Updated usage instructions to reflect slash-only commands.
- `tests/`: Updated test suites to remove deprecated prefix command test cases.
