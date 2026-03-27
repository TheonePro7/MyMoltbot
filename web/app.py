"""
足彩赔率分析 — Web 入口。
默认读取项目根目录下 examples/matches_sample.json，在浏览器中展示多庄对比与逐庄分析。
"""

from __future__ import annotations

import os
from pathlib import Path

from flask import Flask, render_template

from football_odds.analysis import compare_bookmakers, load_matches_from_json

# 项目根目录（web/app.py 的上两级为仓库根时，parent.parent）
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


def _build_view_model():
    """加载示例数据并生成每场比赛的对比结果，供模板渲染。"""
    data_path = os.environ.get("FOOTBALL_ODDS_DATA", str(DEFAULT_DATA))
    path = Path(data_path)
    if not path.is_file():
        return [], f"数据文件不存在: {path}"
    matches = load_matches_from_json(path)
    rows = []
    for m in matches:
        rows.append({"match": m, "compare": compare_bookmakers(m)})
    return rows, None


@app.get("/")
def index():
    matches_data, error = _build_view_model()
    return render_template(
        "index.html",
        matches_data=matches_data,
        error=error,
        data_path=os.environ.get("FOOTBALL_ODDS_DATA", str(DEFAULT_DATA)),
    )


@app.get("/health")
def health():
    return {"ok": True}


def main():
    # 便于 python3 -m web.app 启动
    port = int(os.environ.get("PORT", "5000"))
    host = os.environ.get("HOST", "127.0.0.1")
    app.run(host=host, port=port, debug=os.environ.get("FLASK_DEBUG") == "1")


if __name__ == "__main__":
    main()
