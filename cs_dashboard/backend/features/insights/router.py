# 인사이트 조회·갱신 API 라우터 (3개 엔드포인트). 집계는 compute.py, 저장은 cache.py에 위임한다.
# GET  /api/insights/wings_tickets  : 반복 Wings 티켓 캐시 조회.
# GET  /api/insights/repeat_parents : 학부모 반복 인입 캐시 조회.
# POST /api/insights/refresh        : 즉시 재집계 후 캐시 갱신 — scheduler.py의 update_insights_cache()를 호출해
#                                     Wings 상태 enrichment까지 포함한다.
import json
from fastapi import APIRouter
from features.insights.cache import _read_cache
from features.collection.scheduler import update_insights_cache

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
    await update_insights_cache()
    return {"status": "ok"}
