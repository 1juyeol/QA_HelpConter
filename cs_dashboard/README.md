# CS 대시보드

공감센터(help-desk) CS 데이터를 수집·분석하는 내부 대시보드.
매 시간 자동으로 데이터를 수집하고, 일별·주별·월별 통계와 분류별 드릴다운을 제공한다.

---

## 파일 구조

```
cs_dashboard/
├── backend/               # 서버 — 이전 시 이 폴더째로 복사
│   ├── server.py          # FastAPI 라우트 (API 엔드포인트)
│   ├── db.py              # DB 연결·스키마 초기화
│   ├── helpdesk.py        # help-desk API 클라이언트
│   ├── scheduler.py       # 매 시간 자동 수집 + 키워드 분류
│   ├── classifier.py      # 키워드 기반 CS 분류 로직
│   ├── cs_dashboard.db    # SQLite DB
│   ├── requirements.txt   # Python 패키지 목록
│   └── .env               # 인증 토큰 (공유 금지)
├── frontend/
│   └── index.html         # 대시보드 UI (단일 파일)
├── .gitignore
└── CLAUDE.md              # 개발 가이드 (분류 로직 상세 포함)
```

---

## 아키텍처

```
[help-desk API]
      │  매 시간 수집 (scheduler.py)
      ▼
[SQLite DB]  ←  classifier.py 로 call_memo 키워드 분류
      │
      ▼
[FastAPI]  →  [index.html]
```

- 수집 주기: 매 시간 정각
- 수집 규모: 약 800건/일
- 분류: `call_memo` 텍스트를 키워드로 매칭해 `new_category_main/sub` 결정
- 분류 로직 상세: `CLAUDE.md` 참고

---

## 설치 및 실행

```bash
cd backend
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8000
```

서버 시작 시 터미널에서 help-desk 아이디/비번 입력. 메모리에만 유지되며 파일에 저장되지 않는다.

---

## API 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/api/stats/hourly_range` | 날짜 범위의 시간대별 건수 |
| GET | `/api/stats/daily` | 일별 건수 (주/월별 뷰) |
| GET | `/api/stats/category` | 분류별 건수 |
| GET | `/api/issues` | 상세 목록 (드릴다운) |
| GET | `/api/collection/latest` | 마지막 수집 시각 |

공통 파라미터: `target_date`, `period` (day/week/month), `start_date`, `end_date`

---

## 인증

서버 시작 시 터미널에서 아이디/비번 입력 (`scheduler.py`의 `prompt_credentials()`).
입력값은 메모리에만 유지되며 파일에 저장되지 않는다.
매 수집마다 `POST /account/auths/authenticate_new/`로 자동 로그인해서 토큰 갱신.

---

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

---

## 분류 시스템

call_memo 텍스트를 키워드로 매칭해 `new_category_main/sub`를 결정한다.

### 구성 요소

`backend/classifier.py`에 세 가지 데이터 구조와 하나의 함수로 이루어져 있다.

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

#### 2. `FALLBACK_SUBS` — 예비 소분류

```python
FALLBACK_SUBS = {"교사 상담 요청", "기타"}
```

- **일반 소분류**: 키워드가 매칭되면 항상 분류 결과로 사용됨
- **예비 소분류** (`FALLBACK_SUBS`에 등록된 것): 일반 소분류가 하나도 안 걸렸을 때만 사용됨

```
매칭된 소분류 목록
    └─ 일반 소분류가 있음 → 예비 소분류 전부 무시, 일반 소분류만 사용
    └─ 일반 소분류가 없음 → 예비 소분류 사용
```

예: 메모에 "선생님 전달" + "해지요청" 둘 다 포함
→ `교사 상담 요청`(예비), `해지 상담`(일반) 둘 다 매칭됨
→ 일반 소분류가 있으므로 `교사 상담 요청` 무시
→ 최종: `해지·유지 상담 / 해지 상담`

#### 3. `RULES` — 키워드 규칙 리스트 (순서 있음)

`(소분류명, [키워드, ...])` 형태의 리스트. **리스트 순서가 우선순위**가 된다.
각 소분류에서 키워드는 `in` 연산자로 부분 일치 확인. 키워드 전체 목록은 `classifier.py`의 `RULES`가 정본이다.

#### 4. `classify(memo)` — 분류 실행 함수

`call_memo` 문자열을 받아 `(대분류, 소분류)` 튜플을 반환한다. 미분류 시 `(None, None)`.

```
1. memo가 비어 있으면 → (None, None) 반환
2. RULES를 순서대로 순회 → 키워드 매칭된 소분류 수집
3. matched_subs가 없으면 → (None, None) 반환
4. 폴백 분리: non_fallback이 있으면 폴백 무시, 없으면 폴백 사용
5. 대분류 그룹화: SUB_TO_MAIN으로 변환
6. 대분류가 1개 → 해당 (대분류, 소분류) 반환
7. 대분류가 2개 이상 → 우선순위 순서로 선택
   기타 → 해지·유지 상담 → 네트워크·앱 오류 → 기기·하드웨어 오류
   → 미납·결제 → 체험 관련 → 교재·물류·배송 → 계정·서비스 → 윙크북스
8. caller(scheduler.py)에서 (None, None) 수신 시 기타/기타로 DB에 저장
```

### 분류 규칙 변경

분류 규칙을 변경하면 DB 전체 재적용이 필요하다. 전체 `issues` 레코드에 대해 `classify(call_memo)`를 다시 실행하고 `new_category_main/sub`를 UPDATE한다.

---

## 미구현 항목

- **Teams 알림**: 임계값 기반 이상 감지 알림
- **LLM 보고서**: Ollama 기반 자동 보고서 생성
- **데이터 필터링**: 불필요 분류 제거 (분류 안정화 후 결정)
