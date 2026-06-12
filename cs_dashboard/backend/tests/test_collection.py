# features/collection/client.py의 select_new_issues 유닛 테스트.
# 증분 수집의 핵심 로직: 페이지 결과에서 이미 DB에 있는 ID(known_ids)를 빼고 신규만 남기며,
# 빈 리스트가 나오면 fetch_issues가 페이지네이션을 멈추는 신호가 된다.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from features.collection.client import select_new_issues


def _page(*ids):
    return [{"id": i} for i in ids]


class TestSelectNewIssues:
    def test_filters_known(self):
        new = select_new_issues(_page(10, 11, 12), {11})
        assert [p["id"] for p in new] == [10, 12]

    def test_all_new(self):
        new = select_new_issues(_page(20, 21), set())
        assert [p["id"] for p in new] == [20, 21]

    def test_all_known_returns_empty(self):
        # 전부 기존 ID → 빈 리스트(= 페이지네이션 중단 신호)
        assert select_new_issues(_page(1, 2, 3), {1, 2, 3}) == []
