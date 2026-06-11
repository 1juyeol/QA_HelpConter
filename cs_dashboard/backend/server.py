import asyncio
import json
from datetime import date, timedelta
from pathlib import Path
from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from db import get_conn, init_db
from scheduler import start_scheduler, collect_today, prompt_credentials


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


from insights import compute_wings_tickets, compute_repeat_parents


def _save_insights_cache(wings, parents):
    from datetime import datetime
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_conn() as conn:
        conn.execute("INSERT OR REPLACE INTO insights_cache VALUES (?, ?, ?)",
                     ("wings_tickets", json.dumps(wings, ensure_ascii=False), now))
        conn.execute("INSERT OR REPLACE INTO insights_cache VALUES (?, ?, ?)",
                     ("repeat_parents", json.dumps(parents, ensure_ascii=False), now))
        conn.commit()


def _read_cache(key):
    with get_conn() as conn:
        row = conn.execute("SELECT data, updated_at FROM insights_cache WHERE key=?", (key,)).fetchone()
    return row


@app.on_event("startup")
async def startup():
    prompt_credentials()
    init_db()
    start_scheduler()
    asyncio.create_task(collect_today())
    asyncio.create_task(_init_insights_cache())


async def _init_insights_cache():
    with get_conn() as conn:
        has_cache = conn.execute("SELECT 1 FROM insights_cache LIMIT 1").fetchone()
    if not has_cache:
        end = str(date.today())
        start = str(date.today() - timedelta(days=30))
        _save_insights_cache(compute_wings_tickets(start, end), compute_repeat_parents(start, end))


BUCKET_SQL = """
    CASE
        WHEN CAST(strftime('%H', datetime(created_date, '+9 hours')) AS INTEGER) < 9 THEN '~09:00'
        WHEN CAST(strftime('%H', datetime(created_date, '+9 hours')) AS INTEGER) >= 21 THEN '21:00~'
        ELSE strftime('%H', datetime(created_date, '+9 hours')) || ':' ||
             CASE WHEN CAST(strftime('%M', datetime(created_date, '+9 hours')) AS INTEGER) < 30
                  THEN '00' ELSE '30' END
    END AS bucket
"""
BUCKETS = ['~09:00'] + [f"{h:02d}:{m}" for h in range(9, 21) for m in ('00', '30')] + ['21:00~']


def _bucket_where(bucket: str):
    dt = "datetime(created_date, '+9 hours')"
    h = f"CAST(strftime('%H', {dt}) AS INTEGER)"
    m = f"CAST(strftime('%M', {dt}) AS INTEGER)"
    if bucket == '~09:00':
        return f"{h} < 9", []
    if bucket == '21:00~':
        return f"{h} >= 21", []
    hh, mm = bucket.split(':')
    hh = int(hh)
    if mm == '00':
        return f"({h} = {hh} AND {m} < 30)", []
    return f"({h} = {hh} AND {m} >= 30)", []


# ── 시간별 집계 (날짜 범위) ──────────────────────────────────────
@app.get("/api/stats/hourly_range")
def stats_hourly_range(start_date: str = Query(default=None), end_date: str = Query(default=None)):
    if not end_date:
        end_date = str(date.today())
    if not start_date:
        start_date = end_date
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT {BUCKET_SQL}, COUNT(*) AS count FROM issues "
            "WHERE date(datetime(created_date, '+9 hours')) BETWEEN ? AND ? GROUP BY bucket",
            (start_date, end_date),
        ).fetchall()
    count_map = {r["bucket"]: r["count"] for r in rows}
    return [{"bucket": b, "count": count_map.get(b, 0)} for b in BUCKETS]


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
    bucket: str = Query(default=None),
):
    if start_date and end_date:
        col = "date(datetime(created_date, '+9 hours'))"
        where, params = f"{col} BETWEEN ? AND ?", [start_date, end_date]
    else:
        if not target_date:
            target_date = str(date.today())
        where, params = _period_where(target_date, period)
    if bucket:
        bw, bp = _bucket_where(bucket)
        where += f" AND {bw}"
        params.extend(bp)
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
    unclassified: bool = False,
    limit: int = 200,
    offset: int = 0,
    bucket: str = Query(default=None),
):
    if start_date and end_date:
        col = "date(datetime(created_date, '+9 hours'))"
        where, params = f"{col} BETWEEN ? AND ?", [start_date, end_date]
    else:
        if not target_date:
            target_date = str(date.today())
        where, params = _period_where(target_date, period)
    if bucket:
        bw, bp = _bucket_where(bucket)
        where += f" AND {bw}"
        params.extend(bp)
    if unclassified:
        where += " AND new_category_main IS NULL"
    elif category_main:
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
                   new_category_main, new_category_sub, call_memo,
                   student_id, CASE WHEN parent_id = 92 THEN NULL ELSE parent_id END AS parent_id
            FROM issues WHERE {where}
            ORDER BY created_date DESC LIMIT ? OFFSET ?
            """,
            params + [limit, offset],
        ).fetchall()
    return {"total": total, "items": [dict(r) for r in rows]}


# ── 주별 집계 (4주, 월요일 기준) ─────────────────────────────
@app.get("/api/stats/weekly")
def stats_weekly(target_date: str = Query(default=None)):
    if not target_date:
        target_date = str(date.today())
    d = date.fromisoformat(target_date)
    monday = d - timedelta(days=d.weekday())
    range_start = str(monday - timedelta(days=21))
    range_end = str(monday + timedelta(days=6))
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
            WHERE date(datetime(created_date, '+9 hours')) BETWEEN ? AND ?
            GROUP BY week_start
            ORDER BY week_start
            """,
            (range_start, range_end),
        ).fetchall()
    return [{"week_start": r["week_start"], "count": r["count"]} for r in rows]


# ── 월별 집계 (3개월) ─────────────────────────────────────────
@app.get("/api/stats/monthly")
def stats_monthly(target_date: str = Query(default=None)):
    if not target_date:
        target_date = str(date.today())
    d = date.fromisoformat(target_date)
    target_ym = d.strftime('%Y-%m')
    m, y = d.month - 2, d.year
    if m <= 0:
        m += 12
        y -= 1
    start_ym = f"{y:04d}-{m:02d}"
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT strftime('%Y-%m', datetime(created_date, '+9 hours')) AS month,
                   COUNT(*) AS count
            FROM issues
            WHERE strftime('%Y-%m', datetime(created_date, '+9 hours')) BETWEEN ? AND ?
            GROUP BY month
            ORDER BY month
            """,
            (start_ym, target_ym),
        ).fetchall()
    return [{"month": r["month"], "count": r["count"]} for r in rows]


# ── 인사이트: 캐시 조회 ──────────────────────────────────────
@app.get("/api/insights/wings_tickets")
def insights_wings_tickets():
    row = _read_cache("wings_tickets")
    if not row:
        return {"data": [], "updated_at": None}
    return {"data": json.loads(row["data"]), "updated_at": row["updated_at"]}


@app.get("/api/insights/repeat_parents")
def insights_repeat_parents():
    row = _read_cache("repeat_parents")
    if not row:
        return {"data": [], "updated_at": None}
    return {"data": json.loads(row["data"]), "updated_at": row["updated_at"]}


@app.post("/api/insights/refresh")
async def insights_refresh():
    end = str(date.today())
    start = str(date.today() - timedelta(days=30))
    _save_insights_cache(compute_wings_tickets(start, end), compute_repeat_parents(start, end))
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


_dist = Path(__file__).parent.parent / "frontend" / "dist"
app.mount("/assets", StaticFiles(directory=_dist / "assets"), name="assets")

@app.get("/{full_path:path}", include_in_schema=False)
async def spa_fallback(full_path: str):
    return FileResponse(_dist / "index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.server:app", host="0.0.0.0", port=8000, reload=False)
