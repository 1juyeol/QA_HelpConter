# 통계 집계 API 라우터 (5개 엔드포인트). 모두 GET 요청이며 쿼리 파라미터로 기간을 지정한다.
# hourly_range : 날짜 범위의 30분 버킷별 건수 반환 — 차트 X축 26개 버킷 고정 출력.
# daily        : 일별 건수 (period=day/week/month).
# category     : 대분류·소분류·버킷 조합 필터 집계 — 카테고리 드릴다운용.
# weekly       : 주차별 건수 (최근 4주). monthly : 월별 건수 (최근 3개월).
from datetime import date, timedelta
from fastapi import APIRouter, Query
from core.db import get_conn
from core.utils import BUCKET_SQL, BUCKETS, _bucket_where, _period_where

router = APIRouter()


@router.get("/api/stats/hourly_range")
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


@router.get("/api/stats/daily")
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


@router.get("/api/stats/category")
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


@router.get("/api/stats/weekly")
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


@router.get("/api/stats/monthly")
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
