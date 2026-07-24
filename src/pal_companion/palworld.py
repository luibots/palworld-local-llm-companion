import httpx

from .models import RetrievedSource


def world_to_map(x: float, y: float) -> tuple[float, float]:
    return (y - 158_000.0) / 460.0, (x + 123_000.0) / 460.0


class PalworldClient:
    def __init__(self, base_url: str, admin_password: str):
        self.base_url = base_url.rstrip("/")
        self.auth = httpx.BasicAuth("admin", admin_password) if admin_password else None

    async def live_context(self) -> list[RetrievedSource]:
        if not self.base_url:
            return []
        async with httpx.AsyncClient(timeout=8, auth=self.auth) as client:
            response = await client.get(f"{self.base_url}/v1/api/players")
            response.raise_for_status()
            payload = response.json()
        players = payload.get("players", payload) if isinstance(payload, dict) else payload
        lines: list[str] = []
        for player in players or []:
            name = player.get("name") or player.get("accountName") or "Unknown player"
            x, y = player.get("location_x"), player.get("location_y")
            if x is not None and y is not None:
                map_x, map_y = world_to_map(float(x), float(y))
                lines.append(f"{name}: map coordinates {map_x:.0f}, {map_y:.0f}")
            else:
                lines.append(f"{name}: online, position unavailable")
        if not lines:
            lines.append("No players are currently online.")
        return [
            RetrievedSource(
                source_id="live:players",
                title="Live server players",
                text="\n".join(lines),
                kind="live",
                score=1.0,
            )
        ]
