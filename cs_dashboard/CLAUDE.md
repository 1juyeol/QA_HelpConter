# CLAUDE.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

Tradeoff: These guidelines bias toward caution over speed. For trivial tasks, use judgment.

1. Think Before Coding
Don't assume. Don't hide confusion. Surface tradeoffs.

Before implementing:

State your assumptions explicitly. If uncertain, ask.
If multiple interpretations exist, present them - don't pick silently.
If a simpler approach exists, say so. Push back when warranted.
If something is unclear, stop. Name what's confusing. Ask.
2. Simplicity First
Minimum code that solves the problem. Nothing speculative.

No features beyond what was asked.
No abstractions for single-use code.
No "flexibility" or "configurability" that wasn't requested.
No error handling for impossible scenarios.
If you write 200 lines and it could be 50, rewrite it.
Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

3. Surgical Changes
Touch only what you must. Clean up only your own mess.

When editing existing code:

Don't "improve" adjacent code, comments, or formatting.
Don't refactor things that aren't broken.
Match existing style, even if you'd do it differently.
If you notice unrelated dead code, mention it - don't delete it.
When your changes create orphans:

Remove imports/variables/functions that YOUR changes made unused.
Don't remove pre-existing dead code unless asked.
The test: Every changed line should trace directly to the user's request.

4. Goal-Driven Execution
Define success criteria. Loop until verified.

Transform tasks into verifiable goals:

"Add validation" → "Write tests for invalid inputs, then make them pass"
"Fix the bug" → "Write a test that reproduces it, then make it pass"
"Refactor X" → "Ensure tests pass before and after"
For multi-step tasks, state a brief plan:

1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

These guidelines are working if: fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

---

# CS 대시보드 프로젝트

공감센터(help-desk) CS 데이터를 수집·분석하는 내부 대시보드.
**운영 구조**: `backend/`는 별도 서버에서 실행, `frontend/`는 로컬에서 유지.
서버 이전 시 `backend/` 폴더째로 복사하면 된다 — 필요한 파일이 모두 포함되어 있다.

## 파일 구조

```
cs_dashboard/
├── backend/               # 서버 이전 시 이 폴더째로 복사
│   ├── server.py          # FastAPI 라우트
│   ├── db.py              # DB 연결·스키마
│   ├── helpdesk.py        # help-desk API 클라이언트
│   ├── scheduler.py       # 수집 스케줄러 + 환경변수 로드
│   ├── cs_dashboard.db    # SQLite DB
│   ├── requirements.txt
│   └── .env               # 인증 토큰
├── frontend/
│   └── index.html         # 대시보드 UI
├── .gitignore
└── CLAUDE.md
```

## 실행

```bash
# backend/ 폴더 안에서 실행 (로컬·서버 동일)
cd backend
uvicorn server:app --host 0.0.0.0 --port 8000
```

프론트 서빙이 필요 없으면 `server.py` 마지막 줄 `app.mount(...)` 제거.

## 인증

서버 시작 시 터미널에서 아이디/비번 입력 (`scheduler.py`의 `prompt_credentials()`).
입력값은 메모리에만 유지되며 파일에 저장되지 않는다.
매 수집마다 `POST /account/auths/authenticate_new/`로 자동 로그인해서 토큰 갱신.

## DB 스키마

**issues 테이블**

| 컬럼 | 설명 |
|------|------|
| id | help-desk 원본 ID |
| created_date | 생성일시 (UTC, 조회 시 +9h 변환) |
| category_main | 원본 대분류 — **수정 금지** |
| category_sub | 원본 소분류 — **수정 금지** |
| category_full | 원본 전체 분류 경로 |
| call_memo | 상담 메모 |
| new_category_main | 재분류 대분류 (2026-06 키워드 분류) |
| new_category_sub | 재분류 소분류 (2026-06 키워드 분류) |

`category_main/sub`는 help-desk 시스템에서 내려오는 원본값. 건드리지 않는다.
`new_category_main/sub`가 실제 분석에 사용하는 분류.

프론트엔드는 `new_category_main/sub` 기준으로 동작한다.

**collection_log 테이블**: 수집 이력 (일시, 대상일, 수집건수, 상태)

## 분류 시스템

call_memo 텍스트를 키워드로 매칭해 `new_category_main/sub`를 결정한다.

### 대분류 (9개)

| 대분류 | 소분류 |
|--------|--------|
| 기기·하드웨어 오류 | 충전 불량, 터치·화면 불량, 전원·부팅 오류, 기기 파손, 기기 교체 요청 |
| 네트워크·앱 오류 | 와이파이 오류, 학습 끊김·멈춤, 앱 오류, 화상수업 오류 |
| 해지·유지 상담 | 해지 확정, 해지 방어, 해지 상담, 해지금·위약금 문의, 유료학습종료 |
| 미납·결제 | 미납 관리, 카드 변경, 환불·결제취소, 금액수정요청 |
| 체험 관련 | 체험 취소·미인지, 중복 신청, 체험 로그인 독려 |
| 교재·물류·배송 | 교재 누락·오배송, 배송 처리, 배송 지연·조정, 사은품·이벤트 배송, 기기 장기미회수 |
| 계정·서비스 | 개인정보 변경, 이벤트·혜택 문의 |
| 윙크북스 | 윙크북스, 구독취소 |
| 기타 | 내부 이력, 교사 상담 요청, 기타 |

### 키워드 규칙

실제 규칙은 `backend/classifier.py`의 `RULES` 리스트가 정본이다. 아래는 요약.

```python
# FALLBACK_SUBS: 다른 비폴백 소분류가 없을 때만 적용
FALLBACK_SUBS = {"내부 이력", "교사 상담 요청", "기타"}

RULES = [
    ("해지 확정",          ["해지확정", "[해지확정]", ">해지확정", "해지로 처리요청", "해지처리 요청", "구독취소", "구독 취소"]),
    ("해지 방어",          [">성공", "-성공("]),
    ("해지 상담",          ["차 상담]", "해지방어", "방어 상담", "해지 방어 상담", "해지금", "해지부서", "해지 요청"]),
    ("해지금·위약금 문의", ["위약금 문의", "위약금 얼마", "위약금이 얼마", "해지금 문의", "해지금 확인", "해지시 위약금", "해지금 상쇄", "위약금"]),
    ("충전 불량",          ["충전이 안", "충전 안", "충전불량", "충전이안", "충전잘안", "충전 잘 안", "발열", "충전기 불량", "배터리 소모", "방전이 빨리", "종일충전해도", "방전이 빠르"]),
    ("터치·화면 불량",     ["터치오류", "터치 오류", "고스트터치", "자동터치", "화면 깨", "액정", "화면불량", "볼륨키"]),
    ("전원·부팅 오류",     ["전원이 안", "전원안켜", "부팅 반복", "재부팅 반복", "안켜짐", "안 켜짐", "키면 바로 꺼짐"]),
    ("기기 파손",          ["물을 쏟", "낙하 파손", "파손비용", "파손 비용"]),
    ("기기 교체 요청",     ["*교체학습기", "*교체 학습기"]),          # FALLBACK
    ("와이파이 오류",      ["와이파이연결오류", "와이파이 연결", "WiFi 연결", "인터넷 연결 안", "네트워크 불안정"]),
    ("학습 끊김·멈춤",     ["학습 끊김", "학습끊김", "학습 멈춤", "학습멈춤", "끊김현상", "버벅거림", "버퍼링"]),
    ("앱 오류",            ["공장초기화", "캐시 삭제", "캐시삭제", "앱 오류", "앱오류", "무한 로딩", "무한로딩", "프로그램 오류", "앱 튕김", "앱튕김", "영상 자동 재생", "로그인안됨", "어플 로그인", "비밀번호 초기화", "캐츠홈 진입이"]),
    ("화상수업 오류",      ["화상수업 오류", "화상수업 끊김", "화상코칭 연결", "영상통화 안됨", "수업 중 재부팅"]),
    ("미납 관리",          ["장기미납", "미납 해소", "미납 아웃콜", "정지 해제", "학습정지", "착신정지", "입금 확인", "입금처리", "계좌 납부", "대표계좌 입금"]),
    ("카드 변경",          ["카드 변경", "카드변경", "결제카드 변경", "ARS 변경", "카드 등록", "빌링키 만료"]),
    ("환불·결제취소",      ["환불", "청약철회", "결제 취소 요청", "결제취소 요청", "학습비 반환"]),
    ("금액수정요청",       ["학습비 금액수정"]),
    ("체험 취소·미인지",   ["체험 취소", "체험취소", "수취거부", "오는줄 몰랐", "단말기 오는줄", "가족 반대", "신청건 취소", "업로드취소", "신청 건 취소"]),
    ("중복 신청",          ["중복신청", "중복 신청", "이미 체험진행중"]),
    ("체험 로그인 독려",   ["로그인 독려", "체험 로그인", "로그인 해피콜"]),
    ("교재 누락·오배송",   ["배송누락", "오배송", "도서 누락", "교재 안왔", "책이 안왔", "도서가 안왔", "도서 베송이 안", "발송누락", "잘못 배송"]),
    ("배송 처리",          ["추가배송 추가 완료", "정기배송 추가 완료", "추가배송품목"]),
    ("배송 지연·조정",     ["배송 지연", "배송지연", "배송 중단", "출고 시점 조정", "배송 유예"]),
    ("사은품·이벤트 배송", ["이벤트 선물", "사은품"]),
    ("개인정보 변경",      ["개인정보 삭제", "연락처 수정", "수신거부", "연락처 오등록", "성함 변경"]),
    ("이벤트·혜택 문의",   ["지인추천 혜택", "이벤트 문의", "재가입 혜택", "감사편지", "이벤트 참여"]),
    ("윙크북스",           []),     # 키워드 미정
    ("구독취소",           []),     # 키워드 미정
    ("내부 이력",          ["캐츠에서 상담진행", "캐츠 이력 저장", "캐츠상담", "캐츠홈 상담", "캐츠 상담 진행", "이력 저장", "이력저장", "캐잉 이력", "캐잉이력", "에서 상담진행", "wings.danbiedu.co.kr", "이력 :", "<이력", "번호로 인입", "상담예약 예외 완료처리", "에서 상담 진행", "이력 추가", "자마드 전달"]),  # FALLBACK
    ("부재 처리",          ["부재/sms", "부재/문자", ">부재", "부재 종결", "부재종결", "부재로 문자", "부재로인해"]),  # FALLBACK
    ("지면학습",           ["지면학습", "지면 학습"]),                # FALLBACK
    ("기기 장기미회수",    ["장기미회수", "장기 미회수", "재회수 접수", "회수 요청", "회수 접수", "재회수"]),
    ("교사 상담 요청",     ["담당선생님 상담요청", "담당선생님 전달", "선생님 전달", "선생님께 전달"]),  # FALLBACK
    ("유료학습종료",       ["유종처리"]),
]
```

### 충돌 처리 로직

1. 같은 대분류 내 여러 소분류 매칭 → 리스트 앞쪽(우선순위 높은 것) 선택
2. 해지 확정이 해지 방어보다 rules 앞에 위치 (다중 회차 메모 처리)
3. FALLBACK_SUBS(내부 이력·교사 상담 요청·기타)는 다른 비폴백 분류가 없을 때만 적용
4. 서로 다른 대분류 2개 이상 매칭 → 네트워크·앱 오류 > 기기·하드웨어 오류 > 미납·결제 순 우선, 해당 없으면 `기타/기타`

### 적용 현황 (2026-06 기준)

- 내부 이력: 2,028건 (기타/기타 fallback 분리 후)
- 기타/기타: 1,226건 (키워드 미매칭 순수 fallback)
- 이전: 내부 이력 6,245건 → 키워드 분류 + fallback 재정의로 2,028건까지 감소

분류 규칙을 변경하면 DB에 재적용해야 한다. 재적용 스크립트는 위 키워드 규칙과 충돌 처리 로직을 참고해 작성할 것.

## 미구현 항목

- **Teams 알림**: 임계값 기반 이상 감지 알림
- **LLM 보고서**: Ollama 기반 자동 보고서 생성
- **데이터 필터링**: 불필요 분류 제거 (분류 안정화 후 결정)
