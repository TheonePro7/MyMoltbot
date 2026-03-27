# AGENTS.md

## Cursor Cloud specific instructions

This repository is **MyMoltbot**, a Python Flask application for football (soccer) odds analysis (足彩赔率分析). It provides CLI tools and a web UI for analyzing European decimal odds, comparing bookmakers, simulated betting, and match result tracking.

### Tech stack

- **Python 3.12**, Flask, requests, beautifulsoup4, python-dotenv
- **SQLite** for simulated betting ledger (auto-created at `data/sim_bets.sqlite3`)
- No external database or Docker services required

### Running the application

See `README.md` for full details. Quick reference:

| Task | Command |
|------|---------|
| Install deps | `pip install -r requirements.txt` |
| Run tests | `python3 -m unittest discover -s tests -p 'test_*.py' -v` |
| CLI analyze | `python3 main.py analyze examples/matches_sample.json` |
| CLI compare | `python3 main.py compare examples/matches_sample.json` |
| Web app (dev) | `HOST=0.0.0.0 python3 -m web.app` (serves on port 5000) |
| Health check | `curl http://localhost:5000/health` |

### Non-obvious notes

- The web app loads `.env` automatically via `python-dotenv`. Copy `.env.example` to `.env` and fill in `ODDS_API_KEY` to enable The Odds API data source. Without this key, the default `jc500` (500.com) and `file` data sources still work.
- Use `?source=file` query parameter to fall back to local JSON data (`examples/matches_sample.json`) if network sources are unavailable.
- The SQLite database for simulated bets is auto-created on first use; no migrations needed.
- No linter is currently configured in this repository (no flake8/ruff/pylint config). Tests are the primary quality gate.
- Flask runs in non-debug mode by default; set `FLASK_DEBUG=1` to enable debug/reload mode.

### Historical data module

- **Import historical data**: `python3 -m football_odds.history_import --seasons 20 --leagues main`
  - Downloads CSV from football-data.co.uk, caches locally in `data/csv_cache/`, imports into `data/history.sqlite3`
  - `--leagues main` = E0, E1, SP1, D1, I1, F1 (top-tier 5 leagues + Championship)
  - `--leagues all` = includes lower divisions and additional leagues
  - Already-imported seasons are skipped unless `--force` is used
- **Check stats**: `python3 -m football_odds.history_import --stats`
- **Web browsing**: `/history` page with league filtering, match list, and per-match detail (1X2 odds, Asian handicap, O/U)
- CSV files from football-data.co.uk sometimes have a UTF-8 BOM which is automatically stripped during parsing
- The history database path can be overridden via `HISTORY_DB` environment variable
