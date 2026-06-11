# 인사이트 조회·갱신 API 라우터 (3개 엔드포인트). 집계는 compute.py, 저장은 cache.py에 위임한다.
# GET  /api/insights/wings_tickets  : 반복 Wings 티켓 캐시 조회.
# GET  /api/insights/repeat_parents : 학부모 반복 인입 캐시 조회.
# POST /api/insights/refresh        : 즉시 재집계 후 캐시 갱신 — UI 새로고침 버튼이 이 엔드포인트를 호출한다.
import json
from datetime import date, timedelta
from fastapi import APIRouter
from features.insights.cache import _read_cache, _save_insights_cache
from features.insights.compute import compute_wings_tickets, compute_repeat_parents

router = APIRouter()


@router.get("/api/insights/wings_tickets")
def insights_wings_tickets():
    row = _read_cache("wings_tickets")
    if not row:
        return {"data": [], "updated_at": None}
    return {"data": json.loads(row["data"]), "updated_at": row["updated_at"]}


@router.get("/api/insights/repeat_parents")
def insights_repeat_parents():
    row = _read_cache("repeat_parents")
    if not row:
        return {"data": [], "updated_at": None}
    return {"data": json.loads(row["data"]), "updated_at": row["updated_at"]}


@router.post("/api/insights/refresh")
async def insights_refresh():
    end = str(date.today())
    start = str(date.today() - timedelta(days=30))
    _save_insights_cache(compute_wings_tickets(start, end), compute_repeat_parents(start, end))
    return {"status": "ok"}
