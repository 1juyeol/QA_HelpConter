import asyncio
from datetime import date, timedelta
from pathlib import Path
from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from db import get_conn, init_db
from scheduler import start_scheduler, collect_today, prompt_credentials
from reclassify import run as reclassify_run

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    prompt_credentials()
    init_db()
    start_scheduler()
    asyncio.create_task(collect_today())


# ── 시간대별 (일별 뷰에서 꺾은선용) ──────────────────────────────
@app.get("/api/stats/hourly")
def stats_hourly(target_date: str = Query(default=None)):
    if not target_date:
        target_date = str(date.today())
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT strftime('%H', datetime(created_date, '+9 hours')) AS hour,
                   COUNT(*) AS count
            FROM issues
            WHERE date(datetime(created_date, '+9 hours')) = ?
            GROUP BY hour ORDER BY hour
            """,
            (target_date,),
        ).fetchall()
    count_map = {r["hour"]: r["count"] for r in rows}
    return [{"hour": f"{h:02d}", "count": count_map.get(f"{h:02d}", 0)} for h in range(24)]


# ── 시간별 집계 (날짜 범위) ──────────────────────────────────────
@app.get("/api/stats/hourly_range")
def stats_hourly_range(start_date: str = Query(default=None), end_date: str = Query(default=None)):
    if not end_date:
        end_date = str(date.today())
    if not start_date:
        start_date = end_date
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT strftime('%H', datetime(created_date, '+9 hours')) AS hour,
                   COUNT(*) AS count
            FROM issues
            WHERE date(datetime(created_date, '+9 hours')) BETWEEN ? AND ?
            GROUP BY hour ORDER BY hour
            """,
            (start_date, end_date),
        ).fetchall()
    count_map = {r["hour"]: r["count"] for r in rows}
    return [{"hour": f"{h:02d}", "count": count_map.get(f"{h:02d}", 0)} for h in range(24)]


# ── 일별 (주별/월별 뷰에서 꺾은선용) ────────────────────────────
@app.get("/api/stats/daily")
def stats_daily(target_date: str = Query(default=None), period: str = "week"):
    if not target_date:
        target_date = str(date.today())
    where, params = _period_where(target_date, period)
    with get_conn() as conn:
        rows = conn.execute(
            f"""
            SELECT date(datetime(created_date, '+9 hours')) AS day,
                   COUNT(*) AS count
            FROM issues WHERE {where}
            GROUP BY day ORDER BY day
            """,
            params,
        ).fetchall()
    return [{"date": r["day"], "count": r["count"]} for r in rows]


# ── 카테고리별 집계 ───────────────────────────────────────────
@app.get("/api/stats/category")
def stats_category(
    target_date: str = Query(default=None),
    period: str = "day",
    start_date: str = Query(default=None),
    end_date: str = Query(default=None),
):
    if start_date and end_date:
        col = "date(datetime(created_date, '+9 hours'))"
        where, params = f"{col} BETWEEN ? AND ?", [start_date, end_date]
    else:
        if not target_date:
            target_date = str(date.today())
        where, params = _period_where(target_date, period)
    with get_conn() as conn:
        rows = conn.execute(
            f"""
            SELECT new_category_main, new_category_sub, COUNT(*) AS count
            FROM issues WHERE {where}
            GROUP BY new_category_main, new_category_sub
            ORDER BY new_category_main, count DESC
            """,
            params,
        ).fetchall()
    return [dict(r) for r in rows]


# ── 상세 목록 (드릴다운) ─────────────────────────────────────
@app.get("/api/issues")
def list_issues(
    category_main: str = Query(default=None),
    category_sub: str = Query(default=None),
    target_date: str = Query(default=None),
    period: str = "day",
    start_date: str = Query(default=None),
    end_date: str = Query(default=None),
    limit: int = 200,
    offset: int = 0,
):
    if start_date and end_date:
        col = "date(datetime(created_date, '+9 hours'))"
        where, params = f"{col} BETWEEN ? AND ?", [start_date, end_date]
    else:
        if not target_date:
            target_date = str(date.today())
        where, params = _period_where(target_date, period)
    if category_main:
        where += " AND new_category_main = ?"
        params.append(category_main)
    if category_sub:
        where += " AND new_category_sub = ?"
        params.append(category_sub)
    with get_conn() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM issues WHERE {where}", params).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT id, datetime(created_date, '+9 hours') AS created_date,
                   new_category_main, new_category_sub, call_memo
            FROM issues WHERE {where}
            ORDER BY created_date DESC LIMIT ? OFFSET ?
            """,
            params + [limit, offset],
        ).fetchall()
    return {"total": total, "items": [dict(r) for r in rows]}


# ── 주별 집계 (최근 6주) ─────────────────────────────────────
@app.get("/api/stats/weekly")
def stats_weekly():
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT
                date(
                    datetime(created_date, '+9 hours'),
                    '-' || ((strftime('%w', datetime(created_date, '+9 hours')) + 6) % 7) || ' days'
                ) AS week_start,
                COUNT(*) AS count
            FROM issues
            WHERE date(datetime(created_date, '+9 hours')) >= date(datetime('now', '+9 hours'), '-41 days')
            GROUP BY week_start
            ORDER BY week_start
            """
        ).fetchall()
    return [{"week_start": r["week_start"], "count": r["count"]} for r in rows]


# ── 월별 집계 (최근 3개월) ────────────────────────────────────
@app.get("/api/stats/monthly")
def stats_monthly():
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT strftime('%Y-%m', datetime(created_date, '+9 hours')) AS month,
                   COUNT(*) AS count
            FROM issues
            WHERE date(datetime(created_date, '+9 hours')) >= date(datetime('now', '+9 hours'), 'start of month', '-2 months')
            GROUP BY month
            ORDER BY month
            """
        ).fetchall()
    return [{"month": r["month"], "count": r["count"]} for r in rows]


# ── 미분류 일괄 재분류 ───────────────────────────────────────
@app.post("/api/admin/reclassify")
def admin_reclassify():
    reclassify_run()
    return {"status": "ok"}


# ── 마지막 수집 시각 ──────────────────────────────────────────
@app.get("/api/collection/latest")
def collection_latest():
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM collection_log ORDER BY id DESC LIMIT 1"
        ).fetchone()
    return dict(row) if row else {}


def _period_where(target_date: str, period: str):
    d = date.fromisoformat(target_date)
    col = "date(datetime(created_date, '+9 hours'))"
    if period == "day":
        return f"{col} = ?", [target_date]
    elif period == "week":
        start = str(d - timedelta(days=6))
        return f"{col} BETWEEN ? AND ?", [start, target_date]
    elif period == "month":
        start = str(d.replace(day=1))
        return f"{col} BETWEEN ? AND ?", [start, target_date]
    return "1=1", []


app.mount("/", StaticFiles(directory=Path(__file__).parent.parent / "frontend", html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.server:app", host="0.0.0.0", port=8000, reload=False)
