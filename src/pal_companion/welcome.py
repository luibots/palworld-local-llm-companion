from .models import WelcomeMessage, WelcomeMessageRequest
from .store import VectorStore

WELCOME_TIPS = (
    "PAL Companion can find pals, materials, vendors, and coordinates.",
    "Discord /players shows the live roster and player coordinates.",
    "Discord /getmods has the supported guild mod installer.",
    "Press R in your inventory at a base to use Easy Bulk Storage.",
)


def _clean_text(value: str | None, fallback: str, limit: int) -> str:
    cleaned = " ".join(str(value or fallback).split())
    cleaned = "".join(character for character in cleaned if character.isprintable())
    return cleaned[:limit] or fallback


def _roster_phrase(player_name: str, online_players: list[str]) -> str:
    seen: set[str] = set()
    others: list[str] = []
    for candidate in online_players:
        cleaned = _clean_text(candidate, "Pal", 32)
        normalized = cleaned.casefold()
        if normalized == player_name.casefold() or normalized in seen:
            continue
        seen.add(normalized)
        others.append(cleaned)

    online_count = len(seen) + 1
    if not others:
        return "You are the first player online."
    shown = ", ".join(others[:3])
    if len(others) > 3:
        shown += f" and {len(others) - 3} more"
    return f"You are joining {shown} ({online_count} online)."


class WelcomeMessageService:
    def __init__(self, store: VectorStore):
        self.store = store

    def construct(self, request: WelcomeMessageRequest) -> WelcomeMessage:
        player_name = _clean_text(request.player_name, "Pal", 32)
        server_name = _clean_text(request.server_name, "the server", 48)
        visit_number, _ = self.store.record_player_welcome(
            request.player_key,
            player_name,
        )
        returning = visit_number > 1
        greeting = (
            f"Welcome back, {player_name}!"
            if returning
            else f"Welcome to {server_name}, {player_name}!"
        )
        day = f" World day {request.world_day}." if request.world_day is not None else ""
        roster = _roster_phrase(player_name, request.online_players)
        seed = sum(request.player_key.encode("utf-8")) + (request.world_day or 0) + visit_number
        tip = WELCOME_TIPS[seed % len(WELCOME_TIPS)]
        message = f"{greeting}{day} {roster} Tip: {tip}"
        if len(message) > 240:
            message = f"{greeting}{day} {roster}"
        return WelcomeMessage(
            message=message[:240],
            returning_player=returning,
            visit_number=visit_number,
        )
