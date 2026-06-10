import asyncio
import json
from datetime import date, timedelta
from pathlib import Path
from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from db import get_conn, init_db
from scheduler import start_scheduler, collect_today, prompt_credentials, _get_client
from reclassify import run as reclassify_run

HELPDESK_ISSUES_URL = "https://help-desk-api.wink.co.kr/issue/issues/"

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


# ── 시간대별 (일별 뷰에서 꺾은선용) ──────────────────────────────
@app.get("/api/stats/hourly")
def stats_hourly(target_date: str = Query(default=None)):
    if not target_date:
        target_date = str(date.today())
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT {BUCKET_SQL}, COUNT(*) AS count FROM issues "
            "WHERE date(datetime(created_date, '+9 hours')) = ? GROUP BY bucket",
            (target_date,),
        ).fetchall()
    count_map = {r["bucket"]: r["count"] for r in rows}
    return [{"bucket": b, "count": count_map.get(b, 0)} for b in BUCKETS]


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


# ── 주별 집계 (최근 1달, 월요일 기준) ────────────────────────
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
            WHERE date(datetime(created_date, '+9 hours')) >= date(datetime('now', '+9 hours'), '-30 days')
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


# ── 미분류 일괄 재분류 ───────────────────────────────────────
@app.post("/api/admin/reclassify")
def admin_reclassify():
    reclassify_run()
    return {"status": "ok"}


# ── 학생/학부모 번호 backfill ────────────────────────────────
@app.post("/api/admin/backfill_ids")
async def admin_backfill_ids():
    asyncio.create_task(_backfill_ids())
    return {"status": "started"}


async def _backfill_ids():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT date(created_date) AS d FROM issues "
            "WHERE student_id IS NULL OR parent_id = 92 ORDER BY d"
        ).fetchall()
    dates = [r["d"] for r in rows]
    if not dates:
        print("[backfill] 보완할 데이터 없음")
        return

    print(f"[backfill] 대상 {len(dates)}일 ({dates[0]} ~ {dates[-1]})")
    client = None
    try:
        client = await _get_client()
        for d_str in dates:
            offset = 0
            total = 0
            while True:
                resp = await client.client.get(
                    HELPDESK_ISSUES_URL,
                    params={
                        "model_type": 1009, "is_complete": "true",
                        "limit": 100, "offset": offset,
                        "created_date": f"{d_str},{d_str}",
                        "search": "", "order_by": "-dpo,-id",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                updates = [(r.get("student"), r.get("parent"), r["id"]) for r in data.get("results", [])]
                with get_conn() as conn:
                    conn.executemany(
                        "UPDATE issues SET student_id=?, parent_id=? WHERE id=?", updates
                    )
                    conn.commit()
                total += len(updates)
                if not data.get("next"):
                    break
                offset += 100
                await asyncio.sleep(5)
            print(f"[backfill] {d_str} 완료 — {total}건")
    finally:
        if client:
            await client.close()
    print("[backfill] 전체 완료")


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
