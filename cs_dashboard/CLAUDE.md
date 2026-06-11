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

### 구성 요소

`backend/classifier.py` 에 세 가지 데이터 구조와 하나의 함수로 이루어져 있다.

---

#### 1. `SUB_TO_MAIN` — 소분류 → 대분류 매핑

소분류 이름을 키로 대분류를 값으로 갖는 dict. 소분류 26개, 대분류 9개.

| 대분류 | 소분류 |
|--------|--------|
| 해지·유지 상담 | 해지 확정, 해지 방어, 해지 상담, 해지금·위약금 문의 |
| 기기·하드웨어 오류 | 충전 불량, 터치·화면 불량, 전원·부팅 오류, 기기 파손, 기기 교체 요청 |
| 네트워크·앱 오류 | 와이파이 오류, 학습 끊김·멈춤, 앱 오류 |
| 미납·결제 | 미납 관리, 결제·환불 처리 |
| 체험 관련 | 체험 취소·미인지, 중복 신청, 체험 신청·로그인 독려 |
| 교재·물류·배송 | 누락·오배송, 기기 장기미회수, 배송·회수 처리 |
| 계정·서비스 | 개인정보 변경, 서비스·이벤트 문의 |
| 윙크북스 | 윙크북스, 구독취소 |
| 기타 | 교사 상담 요청, 기타 |

---

#### 2. `FALLBACK_SUBS` — 예비 소분류

```python
FALLBACK_SUBS = {"교사 상담 요청", "기타"}
```

소분류에는 두 종류가 있다.

- **일반 소분류**: 키워드가 매칭되면 항상 분류 결과로 사용됨 (해지 상담, 충전 불량, 앱 오류 등 대부분)
- **예비 소분류** (`FALLBACK_SUBS`에 등록된 것): 일반 소분류가 하나도 안 걸렸을 때만 사용됨

**왜 예비 소분류가 필요한가?**
상담 메모에는 본 용건 외에 부가적인 내용이 섞이는 경우가 많다.
예를 들어 해지 요청 메모 끝에 "담당 선생님께 전달 부탁드립니다"가 붙는 경우,
메모의 실제 목적은 해지 상담이지 교사 전달이 아니다.
이때 `교사 상담 요청`도 같이 걸리면 어느 쪽으로 분류해야 할지 판단이 어려워진다.
`교사 상담 요청`을 예비 소분류로 지정해두면, 더 명확한 분류(해지 상담)가 있을 때는 자동으로 무시된다.

```
매칭된 소분류 목록
    └─ 일반 소분류가 있음 → 예비 소분류 전부 무시, 일반 소분류만 사용
    └─ 일반 소분류가 없음 → 예비 소분류 사용
```

예: 메모에 "선생님 전달" + "해지요청" 둘 다 포함
→ `교사 상담 요청`(예비), `해지 상담`(일반) 둘 다 매칭됨
→ 일반 소분류가 있으므로 `교사 상담 요청` 무시
→ 최종: `해지·유지 상담 / 해지 상담`

예: 메모에 "선생님 전달" 만 포함
→ `교사 상담 요청`(예비) 만 매칭, 일반 소분류 없음
→ 예비 소분류 사용
→ 최종: `기타 / 교사 상담 요청`

---

#### 3. `RULES` — 키워드 규칙 리스트 (순서 있음)

`(소분류명, [키워드, ...])` 형태의 리스트. **리스트 순서가 우선순위**가 된다.
각 소분류에서 키워드는 `in` 연산자로 부분 일치 확인 (대소문자 구분).
키워드 전체 목록은 `classifier.py`의 `RULES`가 정본이다.

---

#### 4. `classify(memo)` — 분류 실행 함수

`call_memo` 문자열을 받아 `(대분류, 소분류)` 튜플을 반환한다. 미분류 시 `(None, None)`.

**실행 순서:**

```
1. memo가 비어 있으면 → (None, None) 반환

2. RULES를 순서대로 순회
   → 각 소분류에서 키워드 하나라도 포함되면 matched_subs에 추가
   → 하나의 소분류는 최대 1회만 추가 (첫 키워드 매칭 시 break)

3. matched_subs가 없으면 → (None, None) 반환

4. 폴백 분리
   non_fallback = matched_subs 에서 FALLBACK_SUBS 제외
   ├─ non_fallback 있음 → candidates = non_fallback  (폴백 소분류 무시)
   └─ non_fallback 없음 → candidates = matched_subs  (폴백만 있으니 그대로 사용)

5. 대분류 그룹화
   candidates를 SUB_TO_MAIN으로 변환 → {대분류: 첫 번째 소분류} dict
   (같은 대분류 내 여러 소분류 매칭 시, RULES 앞쪽 소분류가 선택됨)

6. 대분류가 1개 → 해당 (대분류, 소분류) 반환

7. 대분류가 2개 이상 → 교차 충돌 처리
   ├─ 폴백만 매칭된 경우 → 첫 번째 (대분류, 소분류) 반환
   └─ 비폴백 교차 충돌 → 아래 우선순위 순서로 대분류 선택:
        기타 → 해지·유지 상담 → 네트워크·앱 오류 → 기기·하드웨어 오류
        → 미납·결제 → 체험 관련 → 교재·물류·배송 → 계정·서비스 → 윙크북스
      우선순위에 해당 없으면 → (기타, 기타) 반환

8. caller(scheduler.py)에서 (None, None) 수신 시 기타/기타 로 DB에 저장
```

**핵심 설계 포인트:**

- **해지 확정 vs 해지 방어**: 상담원이 여러 회차 메모를 하나의 memo에 쌓는 경우, "해지 완료"와 "방어 성공"이 같은 memo에 공존할 수 있다. RULES에서 `해지 확정`이 `해지 방어`보다 앞에 있어 해지 확정이 우선됨.
- **교사 상담 요청은 폴백**: 단독 상담 전달 기록은 교사 상담 요청으로 분류되지만, 기기 오류·해지 등과 함께 있으면 해당 카테고리로 흡수됨.
- **기타는 최종 fallback**: 키워드가 전혀 매칭되지 않는 레코드만 기타/기타. 2026-06 Phase 6 기준 3,094건 (전체의 약 15%).

---

### 분류 규칙 변경

분류 규칙을 변경하면 DB 전체 재적용이 필요하다. 재적용은 전체 `issues` 레코드에 대해 `classify(call_memo)`를 다시 실행하고 `new_category_main/sub`를 UPDATE 하는 방식으로 처리한다.

## 미구현 항목

- **Teams 알림**: 임계값 기반 이상 감지 알림
- **LLM 보고서**: Ollama 기반 자동 보고서 생성
- **데이터 필터링**: 불필요 분류 제거 (분류 안정화 후 결정)
