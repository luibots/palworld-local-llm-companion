import httpx

from .models import RetrievedSource


def world_to_map(x: float, y: float) -> tuple[float, float]:
    return (y - 158_000.0) / 460.0, (x + 123_000.0) / 460.0


class PalworldClient:
    def __init__(self, base_url: str, admin_password: str):
        self.base_url = base_url.rstrip("/")
        self.auth = httpx.BasicAuth("admin", admin_password) if admin_password else None

    async def live_context(
        self,
        player_name: str | None = None,
        player_level: int | None = None,
    ) -> list[RetrievedSource]:
        if not self.base_url:
            return _client_player_context(player_name, player_level)
        players = await self._players()
        current = _current_player(players, player_name)
        lines: list[str] = []
        for player in players:
            name = player.get("name") or player.get("accountName") or "Unknown player"
            prefix = "Current player" if player is current else "Online player"
            level = player.get("level")
            if level is None and player is current:
                level = player_level
            level_text = f", level {int(level)}" if level is not None else ", level unavailable"
            x, y = player.get("location_x"), player.get("location_y")
            if x is not None and y is not None:
                map_x, map_y = world_to_map(float(x), float(y))
                lines.append(
                    f"{prefix} {name}{level_text}: map coordinates {map_x:.0f}, {map_y:.0f}"
                )
            else:
                lines.append(f"{prefix} {name}{level_text}: position unavailable")
        if not lines:
            lines.append("No players are currently online.")
        elif current is None and player_level is not None:
            lines.insert(
                0,
                f"Current player {player_name or 'browser pilot'}: level {player_level}; "
                "position unavailable.",
            )
        return [
            RetrievedSource(
                source_id="live:players",
                title="Live server players",
                text="\n".join(lines),
                kind="live",
                score=1.0,
            )
        ]

    async def player_position(self, player_name: str | None) -> tuple[float, float] | None:
        if not self.base_url:
            return None
        players = await self._players()
        current = _current_player(players, player_name)
        if current is None:
            return None
        x, y = current.get("location_x"), current.get("location_y")
        if x is None or y is None:
            return None
        return world_to_map(float(x), float(y))

    async def _players(self) -> list[dict]:
        async with httpx.AsyncClient(timeout=8, auth=self.auth) as client:
            response = await client.get(f"{self.base_url}/v1/api/players")
            response.raise_for_status()
            payload = response.json()
        players = payload.get("players", payload) if isinstance(payload, dict) else payload
        return players or []


def _current_player(
    players: list[dict],
    player_name: str | None,
) -> dict | None:
    if player_name:
        expected = player_name.strip().casefold()
        for player in players:
            names = (player.get("name"), player.get("accountName"))
            if any(str(name).strip().casefold() == expected for name in names if name):
                return player
    if len(players) == 1:
        return players[0]
    return None


def _client_player_context(
    player_name: str | None,
    player_level: int | None,
) -> list[RetrievedSource]:
    if player_level is None:
        return []
    return [
        RetrievedSource(
            source_id="live:current-player",
            title="Current player profile",
            text=(
                f"Current player {player_name or 'browser pilot'}: level {player_level}; "
                "position unavailable."
            ),
            kind="live",
            score=1.0,
        )
    ]
