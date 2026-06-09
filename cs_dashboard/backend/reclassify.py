"""기존 미분류(new_category_main IS NULL) 데이터 일괄 재분류."""
from db import get_conn
from classifier import classify


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
