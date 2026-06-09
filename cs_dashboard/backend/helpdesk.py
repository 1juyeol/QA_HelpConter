import httpx
from datetime import date

BASE_URL = "https://help-desk-api.wink.co.kr"
HEADERS = {
    "accept": "*/*",
    "accept-language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "origin": "https://help-desk.wink.co.kr",
    "referer": "https://help-desk.wink.co.kr/",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/148.0.0.0 Safari/537.36"
    ),
}


class HelpdeskClient:
    def __init__(self, xsrf_token: str, session: str):
        self.client = httpx.AsyncClient(
            headers={**HEADERS, "x-csrftoken": xsrf_token},
            cookies={"XSRF-TOKEN": xsrf_token, "sessionid": session},
            timeout=30,
        )

    @classmethod
    async def login(cls, username: str, password: str) -> "HelpdeskClient":
        async with httpx.AsyncClient(headers=HEADERS, timeout=30) as client:
            resp = await client.post(
                f"{BASE_URL}/account/auths/authenticate_new/",
                json={"username": username, "password": password},
            )
            resp.raise_for_status()
            xsrf = resp.cookies.get("XSRF-TOKEN", "")
            session = resp.cookies.get("sessionid", "")
        return cls(xsrf_token=xsrf, session=session)

    def _parse_issue(self, raw: dict) -> dict:
        data = raw.get("data") or {}
        full_name = data.get("category_tag_full_name", "") or ""
        parts = [p.strip() for p in full_name.split(" / ") if p.strip()]
        call_memo = (data.get("call_history") or {}).get("call_memo", "") or ""
        return {
            "id": raw["id"],
            "created_date": raw.get("created_date"),
            "complete_date": raw.get("complete_date"),
            "category_tag": raw.get("category_tag"),
            "category_main": parts[0] if parts else None,
            "category_sub": parts[-1] if len(parts) > 1 else parts[0] if parts else None,
            "category_full": full_name,
            "call_memo": call_memo,
        }

    async def fetch_issues(self, target_date: date) -> list[dict]:
        date_str = target_date.strftime("%Y-%m-%d")
        all_issues = []
        offset = 0
        limit = 100

        while True:
            resp = await self.client.get(
                f"{BASE_URL}/issue/issues/",
                params={
                    "model_type": 1009,
                    "is_complete": "true",
                    "limit": limit,
                    "offset": offset,
                    "created_date": f"{date_str},{date_str}",
                    "search": "",
                    "order_by": "-dpo,-id",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])
            if not results:
                break
            all_issues.extend(self._parse_issue(r) for r in results)
            if not data.get("next"):
                break
            offset += limit

        return all_issues

    async def close(self):
        await self.client.aclose()
