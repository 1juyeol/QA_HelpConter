# features/issues/classifier.py의 classify() 유닛 테스트.
# 2026-06 기타 흡수용 키워드 보강(기기 교체 요청·누락·오배송)이 의도대로 분류되는지,
# 기존 우선순위(해지 > 기기) 규칙이 보강 후에도 깨지지 않는지(회귀 방지) 검증한다.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from features.issues.classifier import classify


class TestNewKeywords:
    # 보강된 기기 교체 요청 키워드 → 기기·하드웨어 오류로 분류되어야 함
    def test_device_swap_keywords(self):
        for memo in [
            "학습기 교체 요청 주심",
            "재교체 진행하기로 함",
            "정상적으로 교체 접수되었음",
            "교체 받은 학습기 인증화면으로 안 넘어감",
            "터치펜 교체 후 회수 안내",
            "원격 점검 도와드림",
            "점검 부재 / 문자발송",
            "점검 요청 주심",
        ]:
            main, sub = classify(memo)
            assert (main, sub) == ("기기·하드웨어 오류", "기기 교체 요청"), memo

    # 보강된 누락·오배송 키워드
    def test_missing_delivery_keyword(self):
        main, sub = classify("영상 누락되어 재발송 안내")
        assert (main, sub) == ("교재·물류·배송", "누락·오배송")


class TestPriorityRegression:
    # 해지는 기기보다 우선순위가 높다 — 둘 다 매칭돼도 해지로 가야 함
    def test_churn_beats_device(self):
        main, sub = classify("학습기 교체 안내했으나 해지요청 하심")
        assert main == "해지·유지 상담"

    # 같은 기기 대분류 안에서는 RULES 순서(충전이 기기 교체보다 앞)가 우선
    def test_charging_beats_swap_same_main(self):
        main, sub = classify("충전이 안되어 학습기 교체 문의")
        assert (main, sub) == ("기기·하드웨어 오류", "충전 불량")

    # 보강과 무관한 기존 분류는 그대로
    def test_existing_unchanged(self):
        assert classify("와이파이 연결이 안됨")[0] == "네트워크·앱 오류"
        assert classify("위약금 문의 주심")[1] == "해지금·위약금 문의"
        assert classify("") == (None, None)
