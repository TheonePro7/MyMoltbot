"""
足彩赔率分析 — Web 入口。
支持数据源：500 网竞彩（真实 SP）、The Odds API（多庄欧赔）、本地 JSON 示例。
"""

from __future__ import annotations

import os
from pathlib import Path

from flask import Flask, render_template, request

from web.data_service import cst_today_str, load_rows_for_web

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA = ROOT / "examples" / "matches_sample.json"

app = Flask(
    __name__,
    template_folder=str(Path(__file__).resolve().parent / "templates"),
    static_folder=str(Path(__file__).resolve().parent / "static"),
)


@app.template_filter("pct")
def pct_filter(value: float, digits: int = 2) -> str:
    """百分比格式化。"""
    return f"{100.0 * float(value):.{digits}f}%"


@app.get("/")
def index():
    source = request.args.get("source", "jc500").strip()
    jc_date = request.args.get("date")
    rows, error, info = load_rows_for_web(source, jc_date=jc_date)
    data_path = os.environ.get("FOOTBALL_ODDS_DATA", str(DEFAULT_DATA))
    form_jc_date = (jc_date or "").strip() or cst_today_str()
    return render_template(
        "index.html",
        matches_data=rows,
        error=error,
        data_path=data_path,
        source=source,
        jc_date=form_jc_date,
        info=info,
    )


@app.get("/health")
def health():
    return {"ok": True}


def main():
    port = int(os.environ.get("PORT", "5000"))
    host = os.environ.get("HOST", "127.0.0.1")
    app.run(host=host, port=port, debug=os.environ.get("FLASK_DEBUG") == "1")


if __name__ == "__main__":
    main()
