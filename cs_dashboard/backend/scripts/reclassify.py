# 미분류 이슈 일괄 재분류 스크립트.
# new_category_main IS NULL 또는 '미분류'인 issues 행을 모두 조회해 classifier.py 규칙을 적용한다.
# 실행 방법: cd backend && python scripts/reclassify.py
# 주요 흐름: get_conn()으로 미분류 행 조회 → classify(call_memo)로 대분류·소분류 결정
#           → executemany로 new_category_main·new_category_sub 일괄 UPDATE → 결과 출력.
# 의존: core/db.py(get_conn), features/issues/classifier.py(classify)
# 주의: 분류 규칙(RULES) 변경 후 반드시 실행해야 한다 (정책 4).
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.db import get_conn
from features.issues.classifier import classify


def run():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, call_memo FROM issues WHERE new_category_main IS NULL OR new_category_main = '미분류'"
        ).fetchall()

        updates = [(*classify(r["call_memo"]), r["id"]) for r in rows]
        classified = sum(1 for m, s, _ in updates if m is not None)

        conn.executemany(
            "UPDATE issues SET new_category_main = ?, new_category_sub = ? WHERE id = ?",
            updates,
        )
        conn.commit()

    print(f"총 {len(rows)}건 처리 → {classified}건 분류, {len(rows) - classified}건 미분류 유지")


if __name__ == "__main__":
    run()
