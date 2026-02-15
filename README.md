<div align="center">
  <img src="https://github.com/user-attachments/assets/7679c732-1e13-4194-9dc1-b3f981146346" width="200px" alt="Discord LaTeX Bot logo" />
  <h1>Discord LaTeX Bot</h1>
  <p>
    A Discord bot that compiles LaTeX into PNG images so math, physics, and engineering conversations stay readable.
    It is built for study servers, class groups, and anyone who is tired of math getting lost in plain text.
  </p>
</div>

## About the project

I wanted a tool that could render LateX in DMs and on Servers. Addtionally I wanted to be able to generate or copy full Latex documents and have them render too! Heres what it does:

- Reliable rendering for both quick inline math and full document/TikZ snippets
- Fast interaction so the bot does not hang while compiling

## Core Features

- `/latex` compiles LaTeX and posts a rendered PNG
- Supports inline expressions and full-document/TikZ workflows
- Works in servers, DMs, and private channels
- Uses timeout guards during rendering and AI responses
- Local monitoring dashboard with selectable windows (`24h`, `7d`, `30d`, `90d`) and trend charts
- Optional `/talk-to-me` command powered by Google's Gemini ecosystem
- Legacy `latex {LaTeX Code}` message command support in servers

## Technical Highlights

- **Async**: commands run with `asyncio`, and compilation is offloaded via `ThreadPoolExecutor` so the event loop stays responsive.
- **Timeout safety**: rendering and AI calls are wrapped with `asyncio.wait_for` to prevent long-running requests from blocking users.
- **Container-friendly logging**: configurable `LOG_LEVEL`, stdout output, and compose log rotation support.
- **Persistent metrics**: LaTeX compile outcomes are stored in SQLite and visualized in a separate local dashboard service.
- **Linux / Dockerized deployment**: Designed to be deployed on Linux based systems.

## Commands

| Command | Description |
| --- | --- |
| `/latex <latex_code> [dpi]` | Render LaTeX into a PNG image. |
| `/help` | Show command and usage guidance. |
| `/ping` | Health check command. |
| `/talk-to-me <message>` | Optional conversational command (requires Gemini token). |
| `/clear-history` | Clear chat history used by `/talk-to-me`. |
| `latex <latex_code>` | Legacy message-based render command (server messages). |

## Invite Links

- DM install: `https://discord.com/oauth2/authorize?client_id=1242573317693640788`
- Server listing: `https://discordbotlist.com/bots/latex`

## Example Usage

### TikZ Example (full document)

```tex
latex
\documentclass[border=1mm]{standalone}
\usepackage{tikz}
\usepackage{amsmath}
\begin{document}
\begin{tikzpicture}[scale=1.5,>=stealth]
    \draw[->] (-0.5,0) -- (3,0) node[right] {$x$};
    \draw[->] (0,-0.5) -- (0,3) node[above] {$y$};
    \draw[thick, blue] (0,0) -- (2.5,1.5) node[above right] {$\mathbf{v}$};
    \draw[thick, red] (0,0) -- (2,1.2) node[below right] {$\text{proj}_{\mathbf{u}} \mathbf{v}$};
    \draw[dashed] (2,1.2) -- (2.5,1.5);
    \draw[dashed] (2,1.2) -- (2,0);
    \draw[thick] (0,0) -- (2,1.2) node[midway, below left] {$\mathbf{u}$};
    \draw[fill] (2,1.2) circle (1pt);
    \draw[fill] (2.5,1.5) circle (1pt);
\end{tikzpicture}
\end{document}
```

<div align="center">
  <img src="https://github.com/user-attachments/assets/52613cec-0d35-4f66-adcf-ec6cad236121" alt="TikZ render example">
</div>

### Inline Expression Example

```text
/latex \[ \hat{f}(\xi) = \int_{-\infty}^{\infty} f(x) e^{-2\pi i \xi x} \, dx \]
```

<div align="center">
  <img src="https://github.com/user-attachments/assets/a020768e-88ff-4009-b493-aa49d1206899" alt="Inline LaTeX render example">
</div>



## Setup

### Docker (recommended)

1. Create `src/.env` (you can start from `src/.env.example`) with required and optional values:

```env
DISCORD_TOKEN=your_token_here

# Optional: GEMINI_TOKEN=your_token_here

# Optional: used as persistent instruction context for chat responses
SYSTEM_INSTRUCTION=your_system_instruction_here

# Optional: controls Python logging level
LOG_LEVEL=INFO

# Optional: Dashboard auth (required if using monitoring dashboard)
DASHBOARD_USERNAME=your_dashboard_username
DASHBOARD_PASSWORD=your_dashboard_password

# Optional: shared metrics DB path (defaults work in docker compose)
METRICS_DB_PATH=/data/metrics.db

# Optional metrics retention policy (defaults shown)
METRICS_RETENTION_DAYS=90
METRICS_MAX_SIZE_BYTES=536870912
METRICS_MAINTENANCE_INTERVAL_SECONDS=60
```

2. Build and run:

```bash
docker compose up --build
```

3. Run detached / stop:

```bash
docker compose up -d --build
docker compose down
```

4. View logs:

```bash
docker compose logs -f latex-bot
docker compose logs -f dashboard
```

5. Open the monitoring dashboard (local network):

```text
http://<pi-lan-ip>:8081
```

Use `DASHBOARD_USERNAME` and `DASHBOARD_PASSWORD` when prompted.

### Local run (no Docker)

```bash
python -m venv .venv
.venv\\Scripts\\activate
pip install -r src/requirements.txt
python src/bot.py
```

Note: local rendering requires a working LaTeX toolchain available to the host environment (TexLive).

### Quick Testing Suite

Run these quick checks after code changes:

```bash

python -m unittest tests.test_latex_module
python -m unittest tests.test_metrics_store
python -m unittest tests.test_dashboard_api
```

## Usage Notes

- If you include a full `\documentclass ...` block, the bot treats it as a document render path.
- For standard inline usage, include delimiters such as `$...$`, `$$...$$`, or `\[...\]`.
- Large requests and high DPI are constrained to protect responsiveness.

## Local Monitoring Dashboard

- The dashboard runs as a separate service in `monitoring/dashboard`.
- It tracks LaTeX command attempts, successes, failures, and error rates across selectable ranges (`24h`, `7d`, `30d`, `90d`).
- It includes line charts for request/success/error totals, error-status trends, and request counts by source.
- Metrics are stored in `monitoring/data/metrics.db` (via docker volume mount).
- Metrics retention defaults to 90 days and enforces a 512MB SQLite cap by pruning oldest rows when needed.
- Access is local-network only unless you explicitly port-forward your router.
- `0.0.0.0` is a bind address, not a browser URL. Use `localhost` or your Pi LAN IP in the browser.



## Credits

- Built and maintained by @SleepyPandas
- LaTeX HTTP rendering support inspired by and built with [YtoTech Latex to PNG HTTP](https://github.com/YtoTech/latex-on-http)
- Thanks to my friend Indy for support and testing help

## Bonus
It is also Samsung fridge compatible!

&nbsp;

<div align="center">
  <img src="https://github.com/user-attachments/assets/dfa67b5b-9978-4544-bfc3-c3cba668f031" alt="Samsung fridge compatibility badge">
</div>
