import getpass
import json
from datetime import date, datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import pytz

from helpdesk import HelpdeskClient
from db import get_conn
from classifier import classify
from insights import compute_wings_tickets, compute_repeat_parents

KST = pytz.timezone("Asia/Seoul")

_username: str = ""
_password: str = ""


def prompt_credentials():
    global _username, _password
    print("\nhelp-desk 로그인")
    _username = input("  아이디: ")
    _password = getpass.getpass("  비밀번호: ")
    print()


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
                main, sub = "기타", "내부 이력"
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

    # 자정(00:00)에는 어제 23시대 누락분 보정
    if datetime.now(KST).hour == 0:
        yesterday = today - timedelta(days=1)
        await collect_date(yesterday)


async def update_insights_cache():
    end = str(date.today())
    start = str(date.today() - timedelta(days=30))
    wings = compute_wings_tickets(start, end)
    parents = compute_repeat_parents(start, end)
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
    with get_conn() as conn:
        conn.execute("INSERT OR REPLACE INTO insights_cache VALUES (?, ?, ?)",
                     ("wings_tickets", json.dumps(wings, ensure_ascii=False), now))
        conn.execute("INSERT OR REPLACE INTO insights_cache VALUES (?, ?, ?)",
                     ("repeat_parents", json.dumps(parents, ensure_ascii=False), now))
        conn.commit()
    print(f"[{now}] insights cache updated")


def start_scheduler():
    scheduler = AsyncIOScheduler(timezone=KST)
    scheduler.add_job(collect_today, "cron", minute=0)              # 매 정시 수집
    scheduler.add_job(collect_today, "cron", hour="9-20", minute=30) # 09:30~20:30 30분 단위
    scheduler.add_job(update_insights_cache, "cron", hour=0, minute=0)  # 자정 인사이트 캐시
    scheduler.start()
    return scheduler
