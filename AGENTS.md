# AGENTS.md

## Cursor Cloud specific instructions

This repository is **MyMoltbot**, a Python-based football (soccer) odds analysis and prediction system. It includes a Flask web UI, CLI tools, a historical odds database (46K+ matches), a multi-bookmaker data pipeline, and an XGBoost prediction model.

### Tech stack

- **Python 3.12**, Flask, requests, beautifulsoup4, python-dotenv
- **XGBoost**, scikit-learn, pandas, numpy (AI prediction)
- **SQLite** for all data storage (no external DB required)

### Running the application

See `README.md` for full details. Quick reference:

| Task | Command |
|------|---------|
| Install deps | `pip install -r requirements.txt` |
| Run tests | `python3 -m unittest discover -s tests -p 'test_*.py' -v` |
| CLI analyze | `python3 main.py analyze examples/matches_sample.json` |
| Web app (dev) | `HOST=0.0.0.0 python3 -m web.app` (port 5000) |
| Health check | `curl http://localhost:5000/health` |
| Import history (20 seasons) | `python3 -m football_odds.history_import --seasons 20 --leagues main` |
| Snapshot live odds (54+ bookmakers) | `python3 -m football_odds.odds_api_v2` |
| Train model + backtest | `python3 -m ai.train --backtest` |
| DB stats | `python3 -m football_odds.history_import --stats` |

### Non-obvious notes

- The web app loads `.env` automatically via `python-dotenv`. Copy `.env.example` to `.env` and fill in `ODDS_API_KEY` to enable The Odds API data source. Without this key, the `jc500` (500.com) and `file` data sources still work.
- Use `?source=file` query parameter to fall back to local JSON data when network sources are unavailable.
- All SQLite databases are auto-created on first use; no migrations needed. Paths:
  - `data/sim_bets.sqlite3` — simulated betting ledger
  - `data/history.sqlite3` — historical odds (46K+ matches, 580K+ odds records)
- CSV files from football-data.co.uk sometimes have a UTF-8 BOM; the parser strips it automatically.
- The `HISTORY_DB` env var overrides the history database path.
- No linter is configured; tests (`python3 -m unittest discover -s tests`) are the primary quality gate.
- Flask runs in non-debug mode by default; set `FLASK_DEBUG=1` for auto-reload.
- The XGBoost model is saved to `data/models/` after training. It can be loaded via `MatchPredictor.load()`.
- Historical data import is idempotent — already-imported seasons are skipped unless `--force` is used.
- The Odds API free tier has 500 requests/month; `python3 -m football_odds.odds_api_v2` uses ~6 requests per snapshot (one per league).
- The AI backtest uses time-series split (not random), so training data always precedes test data chronologically.
- The model's backtest accuracy (60.3%) includes match statistics features (shots, corners) that are only available post-match. For pre-match prediction, only odds-based features are used, which yields slightly lower but still significant accuracy improvement over the raw odds baseline (52.4%).
- **与用户交流一律使用中文**，代码注释也使用中文。
