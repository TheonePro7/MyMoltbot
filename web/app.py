"""
足彩 Web：真实竞彩 SP、The Odds API、简易预测、模拟投注（胆拖/几串几）、赛果与盈亏。
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from flask import Flask, flash, redirect, render_template, request, url_for

from football_odds.jc_rows import iter_selections
from football_odds.jc500 import fetch_jc_rows
from football_odds.models import BookmakerLine
from football_odds.parlay import list_combo_options_for_n
from football_odds.simple_predict import predict_from_single_line
from web.bet_store import (
    connect,
    create_session,
    create_slip,
    get_or_create_default_session,
    get_results_map,
    list_sessions,
    list_slips,
    session_summary,
    settle_pending_for_session,
    settle_slip,
    set_result,
)
from web.data_service import cst_today_str, load_rows_for_web

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA = ROOT / "examples" / "matches_sample.json"

app = Flask(
    __name__,
    template_folder=str(Path(__file__).resolve().parent / "templates"),
    static_folder=str(Path(__file__).resolve().parent / "static"),
)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-sim-bet-change-me")


@app.template_filter("pct")
def pct_filter(value: float, digits: int = 2) -> str:
    return f"{100.0 * float(value):.{digits}f}%"


@app.template_filter("money")
def money_filter(x: float) -> str:
    return f"{float(x):.2f}"


def _selection_map_for_date(jc_date: str) -> dict[str, dict]:
    rows = fetch_jc_rows(jc_date)
    m: dict[str, dict] = {}
    for jr in rows:
        for s in iter_selections(jr):
            m[s["selection_id"]] = s
    return m


def _validate_slip_selections(sels: list[dict]) -> None:
    seen_f: set[str] = set()
    for s in sels:
        fid = s.get("fixture_id")
        if not fid:
            raise ValueError("选项缺少 fixture_id")
        if fid in seen_f:
            raise ValueError("同一场比赛只能选一个玩法选项（胜平负或让球任选其一）")
        seen_f.add(fid)


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


@app.get("/predict")
def predict_page():
    jc_date = (request.args.get("date") or cst_today_str()).strip()
    rows = fetch_jc_rows(jc_date)
    predictions: list[dict] = []
    for jr in rows:
        if jr.nspf:
            line = BookmakerLine("体彩SP·胜平负", *(
                next(sp for v, sp in jr.nspf if v == "3"),
                next(sp for v, sp in jr.nspf if v == "1"),
                next(sp for v, sp in jr.nspf if v == "0"),
            ))
            p = predict_from_single_line(line)
            predictions.append(
                {
                    "kind": "胜平负",
                    "matchnum": jr.matchnum,
                    "fixture_id": jr.fixture_id,
                    "home": jr.home_team,
                    "away": jr.away_team,
                    "league": jr.league,
                    "kickoff": jr.kickoff,
                    "prediction": p,
                }
            )
        if jr.spf:
            h = next(sp for v, sp in jr.spf if v == "3")
            d = next(sp for v, sp in jr.spf if v == "1")
            a = next(sp for v, sp in jr.spf if v == "0")
            line = BookmakerLine(f"体彩SP·让球{jr.handicap}", h, d, a)
            p = predict_from_single_line(line)
            predictions.append(
                {
                    "kind": f"让球{jr.handicap}",
                    "matchnum": jr.matchnum,
                    "fixture_id": jr.fixture_id,
                    "home": jr.home_team,
                    "away": jr.away_team,
                    "league": jr.league,
                    "kickoff": jr.kickoff,
                    "prediction": p,
                }
            )
    return render_template("predict.html", jc_date=jc_date, predictions=predictions)


@app.get("/bet")
def bet_wizard():
    jc_date = (request.args.get("date") or cst_today_str()).strip()
    rows = fetch_jc_rows(jc_date)
    selections: list[dict] = []
    for jr in rows:
        selections.extend(iter_selections(jr))
    with connect() as conn:
        sid = get_or_create_default_session(conn)
        sessions = list_sessions(conn)
    combo_preview_n = 0
    return render_template(
        "bet_wizard.html",
        jc_date=jc_date,
        selections=selections,
        sessions=sessions,
        session_id=sid,
        combo_preview_n=combo_preview_n,
        combo_options=[],
        max_combo_types=5,
        stake_default=2.0,
    )


@app.post("/bet")
def bet_submit():
    jc_date = (request.form.get("jc_date") or cst_today_str()).strip()
    session_id = (request.form.get("session_id") or "").strip()
    sel_ids = request.form.getlist("selection_id")
    dan_ids = set(request.form.getlist("dan_id"))
    combo_types = [x.strip() for x in request.form.getlist("combo_type") if x.strip()]
    try:
        mult = int(request.form.get("multiplier") or "1")
    except ValueError:
        mult = 1
    try:
        stake = float(request.form.get("stake_per_line") or "2")
    except ValueError:
        stake = 2.0
    if mult < 1:
        mult = 1
    if stake <= 0:
        stake = 2.0
    if len(combo_types) > 5:
        flash("组合过关最多选择 5 种", "error")
        return redirect(url_for("bet_wizard", date=jc_date))
    smap = _selection_map_for_date(jc_date)
    sels = []
    for i in sel_ids:
        if i in smap:
            sels.append(dict(smap[i]))
    try:
        _validate_slip_selections(sels)
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for("bet_wizard", date=jc_date))
    if not sels:
        flash("请至少勾选一注", "error")
        return redirect(url_for("bet_wizard", date=jc_date))
    dan_list = [d for d in dan_ids if d in {x["selection_id"] for x in sels}]
    try:
        with connect() as conn:
            if not session_id:
                session_id = get_or_create_default_session(conn)
            slip_id = create_slip(
                conn,
                session_id,
                jc_date,
                sels,
                combo_types,
                dan_list,
                multiplier=mult,
                stake_per_line=stake,
            )
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for("bet_wizard", date=jc_date))
    flash(f"已保存方案 {slip_id[:8]}…，每子注 {stake * mult:.2f} 元", "ok")
    return redirect(url_for("slip_detail", slip_id=slip_id))


@app.get("/slips")
def slips_list():
    with connect() as conn:
        sid = request.args.get("session_id")
        if not sid:
            sid = get_or_create_default_session(conn)
        sessions = list_sessions(conn)
        slips = list_slips(conn, sid)
        summ = session_summary(conn, sid)
    return render_template(
        "slips.html",
        sessions=sessions,
        session_id=sid,
        slips=slips,
        summary=summ,
    )


@app.post("/session/new")
def session_new():
    name = (request.form.get("name") or "新账本").strip()
    with connect() as conn:
        sid = create_session(conn, name)
    flash("已新建账本", "ok")
    return redirect(url_for("slips_list", session_id=sid))


@app.get("/slips/<slip_id>")
def slip_detail(slip_id: str):
    with connect() as conn:
        row = conn.execute("SELECT * FROM slips WHERE id=?", (slip_id,)).fetchone()
    if not row:
        flash("方案不存在", "error")
        return redirect(url_for("slips_list"))
    slip = dict(row)
    slip["selections"] = json.loads(slip["selections_json"])
    slip["combo_types"] = json.loads(slip["combo_types_json"])
    slip["dan_ids"] = json.loads(slip["dan_ids_json"])
    slip["subbets"] = json.loads(slip["subbets_json"] or "[]")
    return render_template("slip_detail.html", slip=slip)


@app.post("/slips/<slip_id>/settle")
def slip_settle(slip_id: str):
    with connect() as conn:
        try:
            settle_slip(conn, slip_id)
        except ValueError as e:
            flash(str(e), "error")
            return redirect(url_for("slips_list"))
    flash("已结算该方案", "ok")
    return redirect(url_for("slip_detail", slip_id=slip_id))


@app.post("/slips/settle_all")
def settle_all():
    sid = (request.form.get("session_id") or "").strip()
    with connect() as conn:
        if not sid:
            sid = get_or_create_default_session(conn)
        n = settle_pending_for_session(conn, sid)
    flash(f"已尝试结算 {n} 笔待结算方案", "ok")
    return redirect(url_for("slips_list", session_id=sid))


@app.get("/results")
def results_page():
    jc_date = (request.args.get("date") or cst_today_str()).strip()
    rows = fetch_jc_rows(jc_date)
    with connect() as conn:
        existing = get_results_map(conn)
    return render_template(
        "results.html",
        jc_date=jc_date,
        rows=rows,
        existing=existing,
    )


@app.post("/results/import")
def results_import():
    jc_date = (request.form.get("jc_date") or cst_today_str()).strip()
    n = 0
    with connect() as conn:
        for jr in fetch_jc_rows(jc_date):
            if not jr.score_text:
                continue
            m = re.match(r"^(\d+):(\d+)$", jr.score_text.strip())
            if not m:
                continue
            set_result(conn, jr.fixture_id, int(m.group(1)), int(m.group(2)))
            n += 1
    flash(f"已从页面比分导入 {n} 场赛果（按 fid 写入）", "ok")
    return redirect(url_for("results_page", date=jc_date))


@app.post("/results/save")
def results_save():
    jc_date = (request.form.get("jc_date") or cst_today_str()).strip()
    with connect() as conn:
        for key, val in request.form.items():
            if not key.startswith("hg_"):
                continue
            fid = key[3:]
            try:
                hg = int(val)
                ag = int(request.form.get(f"ag_{fid}", "0"))
            except ValueError:
                continue
            set_result(conn, fid, hg, ag)
    flash("赛果已保存", "ok")
    return redirect(url_for("results_page", date=jc_date))


@app.get("/health")
def health():
    return {"ok": True}


def main():
    port = int(os.environ.get("PORT", "5000"))
    host = os.environ.get("HOST", "127.0.0.1")
    app.run(host=host, port=port, debug=os.environ.get("FLASK_DEBUG") == "1")


if __name__ == "__main__":
    main()
