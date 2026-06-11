# 수집 이력 API 라우터 (1개 엔드포인트).
# GET /api/collection/latest: collection_log 테이블에서 가장 최근 수집 기록 1건을 반환한다.
# 헤더에 표시되는 "마지막 수집: HH:MM" 텍스트의 데이터 소스이며, App.tsx에서 60초마다 폴링한다.
from fastapi import APIRouter
from core.db import get_conn

router = APIRouter()


@router.get("/api/collection/latest")
def collection_latest():
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM collection_log ORDER BY id DESC LIMIT 1"
        ).fetchone()
    return dict(row) if row else {}
