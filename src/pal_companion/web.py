import httpx

from .models import RetrievedSource


class BraveSearchClient:
    endpoint = "https://api.search.brave.com/res/v1/web/search"

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def search(self, query: str, limit: int = 5) -> list[RetrievedSource]:
        if not self.api_key:
            return []
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                self.endpoint,
                params={"q": query, "count": limit, "safesearch": "moderate"},
                headers={
                    "Accept": "application/json",
                    "X-Subscription-Token": self.api_key,
                },
            )
            response.raise_for_status()
            results = response.json().get("web", {}).get("results", [])
        return [
            RetrievedSource(
                source_id=f"web:{index + 1}",
                title=item.get("title") or item.get("url") or "Web result",
                text=item.get("description") or "",
                url=item.get("url"),
                kind="web",
                score=max(0.5, 0.9 - index * 0.08),
            )
            for index, item in enumerate(results[:limit])
            if item.get("url")
        ]
