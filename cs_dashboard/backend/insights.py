import re
from collections import defaultdict
from db import get_conn

WINGS_TICKET_RE = re.compile(r'wings\.danbiedu\.co\.kr/#ticket/zoom/(\d+)')


def compute_wings_tickets(start_date: str, end_date: str, limit: int = 50) -> list:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT datetime(created_date, '+9 hours') AS kst_date, call_memo
            FROM issues
            WHERE date(datetime(created_date, '+9 hours')) BETWEEN ? AND ?
              AND call_memo LIKE '%wings.danbiedu.co.kr/#ticket/zoom/%'
            ORDER BY kst_date DESC
            """,
            (start_date, end_date),
        ).fetchall()

    counts = defaultdict(lambda: {"cs_count": 0, "latest_date": None, "first_date": None, "memos": []})
    for r in rows:
        for ticket_id in WINGS_TICKET_RE.findall(r["call_memo"] or ""):
            entry = counts[ticket_id]
            entry["cs_count"] += 1
            if entry["latest_date"] is None:
                entry["latest_date"] = r["kst_date"]
            entry["first_date"] = r["kst_date"]
            entry["memos"].append({"date": r["kst_date"], "memo": r["call_memo"]})

    result = [
        {"ticket_id": tid, "cs_count": info["cs_count"], "latest_date": info["latest_date"],
         "first_date": info["first_date"], "memos": info["memos"]}
        for tid, info in counts.items()
        if info["cs_count"] > 1
    ]
    result.sort(key=lambda x: -x["cs_count"])
    return result[:limit]


def compute_repeat_parents(start_date: str, end_date: str, limit: int = 100) -> list:
    col = "date(datetime(created_date, '+9 hours'))"
    with get_conn() as conn:
        repeat_ids = {
            r["parent_id"]: r["cnt"]
            for r in conn.execute(
                f"""
                SELECT parent_id, COUNT(*) AS cnt
                FROM issues
                WHERE {col} BETWEEN ? AND ?
                  AND parent_id > 100000
                GROUP BY parent_id HAVING cnt >= 2
                ORDER BY cnt DESC LIMIT ?
                """,
                (start_date, end_date, limit),
            ).fetchall()
        }
        if not repeat_ids:
            return []

        placeholders = ",".join("?" * len(repeat_ids))
        rows = conn.execute(
            f"""
            SELECT parent_id,
                   datetime(created_date, '+9 hours') AS kst_date,
                   call_memo, new_category_main, new_category_sub
            FROM issues
            WHERE {col} BETWEEN ? AND ?
              AND parent_id > 100000
              AND parent_id IN ({placeholders})
            ORDER BY parent_id, kst_date DESC
            """,
            (start_date, end_date, *repeat_ids.keys()),
        ).fetchall()

    grouped = defaultdict(lambda: {"cs_count": 0, "latest_date": None, "memos": [], "categories": set()})
    for r in rows:
        entry = grouped[r["parent_id"]]
        entry["cs_count"] += 1
        if entry["latest_date"] is None:
            entry["latest_date"] = r["kst_date"]
        cat = " > ".join(filter(None, [r["new_category_main"], r["new_category_sub"]]))
        entry["memos"].append({"date": r["kst_date"], "memo": r["call_memo"], "category": cat})
        if r["new_category_main"]:
            entry["categories"].add(r["new_category_main"])

    result = [
        {"parent_id": pid, "cs_count": info["cs_count"], "latest_date": info["latest_date"],
         "memos": info["memos"], "categories": list(info["categories"])}
        for pid, info in grouped.items()
    ]
    result.sort(key=lambda x: -x["cs_count"])
    return result
