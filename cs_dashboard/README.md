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
