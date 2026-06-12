# APScheduler 기반 자동 수집 스케줄러. 서버 시작 시 start_scheduler()를 한 번 호출한다.
# 수집 주기: 매 정시(xx:00) 오늘치 수집 / 09:30~20:30 매 30분 단위 오늘치 재수집.
# 자정(00:00): 어제 23시대 누락 데이터 보정 + 인사이트 캐시 갱신.
# 자격증명(_username, _password)은 서버 시작 시 prompt_credentials()로 입력받아 전역 변수에 보관한다.
# _wings_token: Wings(Zammad) API 토큰. 인사이트 캐시 갱신 시 티켓 상태를 실시간으로 조회하는 데 사용한다.
# collect_date()는 성공·실패 모두 collection_log 테이블에 기록해 수집 이력을 추적한다.
import asyncio
import getpass
from datetime import date, datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import httpx
import pytz

from features.collection.client import HelpdeskClient
from core.db import get_conn
from features.issues.classifier import classify
from features.insights.compute import compute_wings_tickets, compute_repeat_parents
from features.insights.cache import _save_insights_cache

KST = pytz.timezone("Asia/Seoul")

_username: str = ""
_password: str = ""
_wings_token: str = ""

# state_id → 한국어 상태명 (Wings/Zammad 기준)
_WINGS_STATE = {1: "신규", 2: "진행 중", 4: "해결", 5: "merged", 7: "요청취소", 8: "결과 확인 중"}


def prompt_credentials():
    global _username, _password, _wings_token
    print("\nhelp-desk 로그인")
    _username = input("  아이디: ")
    _password = getpass.getpass("  비밀번호: ")
    _wings_token = input("  Wings API 토큰 (없으면 엔터): ").strip()
    print()


async def _fetch_wings_states(ticket_ids: list) -> dict:
    """Wings API로 티켓 상태를 비동기 병렬 조회한다. 토큰이 없으면 빈 dict 반환."""
    if not _wings_token:
        return {}
    headers = {"Authorization": f"Token token={_wings_token}"}
    async with httpx.AsyncClient(timeout=10) as client:
        responses = await asyncio.gather(
            *[client.get(f"https://wings.danbiedu.co.kr/api/v1/tickets/{tid}", headers=headers)
              for tid in ticket_ids],
            return_exceptions=True,
        )
    result = {}
    for tid, resp in zip(ticket_ids, responses):
        if isinstance(resp, Exception) or resp.status_code != 200:
            result[str(tid)] = "확인불가"
        else:
            state_id = resp.json().get("state_id")
            result[str(tid)] = _WINGS_STATE.get(state_id, "알 수 없음")
    return result


async def _get_client() -> HelpdeskClient:
    return await HelpdeskClient.login(_username, _password)


async def collect_date(target: date):
    status = "success"
    message = ""
    count = 0
    client = None
    try:
        client = await _get_client()
        issues = await client.fetch_issues(target)
        count = len(issues)
        for issue in issues:
            main, sub = classify(issue.get("call_memo", ""))
            if main is None:
                main, sub = "기타", "기타"
            issue["new_category_main"] = main
            issue["new_category_sub"] = sub
        with get_conn() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO issues
                    (id, created_date, complete_date, category_tag,
                     category_main, category_sub, category_full, call_memo,
                     new_category_main, new_category_sub, student_id, parent_id)
                VALUES
                    (:id, :created_date, :complete_date, :category_tag,
                     :category_main, :category_sub, :category_full, :call_memo,
                     :new_category_main, :new_category_sub, :student_id, :parent_id)
                """,
                issues,
            )
            conn.commit()
    except Exception as e:
        status = "error"
        message = str(e)
    finally:
        if client:
            await client.close()
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO collection_log (date_target, count_fetched, status, message) VALUES (?, ?, ?, ?)",
                (str(target), count, status, message),
            )
            conn.commit()

    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] [{target}] collected {count} issues - {status}" + (f": {message}" if message else ""))


async def collect_today():
    today = date.today()
    await collect_date(today)

    # 자정(00:00)에는 어제 23시대 누락분 보정 후 인사이트 캐시 갱신
    if datetime.now(KST).hour == 0:
        yesterday = today - timedelta(days=1)
        await collect_date(yesterday)
        await update_insights_cache()


async def update_insights_cache():
    end = str(date.today())
    start = str(date.today() - timedelta(days=30))
    wings = compute_wings_tickets(start, end)
    parents = compute_repeat_parents(start, end)
    if wings:
        states = await _fetch_wings_states([t["ticket_id"] for t in wings])
        for t in wings:
            t["state"] = states.get(str(t["ticket_id"]), "확인불가")
        wings = [t for t in wings if t["state"] not in ("해결", "요청취소", "merged")]
    _save_insights_cache(wings, parents)
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] insights cache updated")


def start_scheduler():
    scheduler = AsyncIOScheduler(timezone=KST)
    scheduler.add_job(collect_today, "cron", minute=0)               # 매 정시 수집 (자정엔 어제 보정 + 캐시 갱신 포함)
    scheduler.add_job(collect_today, "cron", hour="9-20", minute=30) # 09:30~20:30 30분 단위
    scheduler.start()
    return scheduler
