import hashlib
import json
import re
from collections import defaultdict

import httpx

from .models import (
    StorageContainerSnapshot,
    StorageMove,
    StoragePlan,
    StorageSnapshotRequest,
)
from .ollama import OllamaClient

STORAGE_SYSTEM_PROMPT = """You route Palworld item stacks into player-labeled chests.
Return JSON only, with this exact shape:
{"routes":[{"item_id":"exact input id","target_container_id":"exact input id",
"confidence":"high|medium","reason":"short reason"}]}
Use only item IDs and target container IDs present in the input. A chest label is the
player's routing instruction. Omit ambiguous items. Never invent IDs."""

CATEGORY_TERMS = {
    "mining": {
        "ore",
        "coal",
        "sulfur",
        "sulphur",
        "quartz",
        "stone",
        "paldium",
        "ingot",
        "metal",
        "oil",
        "chromite",
    },
    "wood": {"wood", "fiber", "fibre", "charcoal", "bamboo"},
    "food": {
        "food",
        "berry",
        "meat",
        "milk",
        "wheat",
        "flour",
        "lettuce",
        "tomato",
        "mushroom",
        "honey",
        "cake",
        "bread",
    },
    "medicine": {"medicine", "medical", "remedy", "potion", "elixir"},
    "pal_material": {
        "organ",
        "leather",
        "bone",
        "horn",
        "wool",
        "fluid",
        "venom",
        "feather",
    },
    "sphere": {"sphere", "capture"},
    "ammo": {"ammo", "bullet", "rocket", "arrow", "missile", "cartridge"},
    "weapon": {"weapon", "gun", "rifle", "sword", "spear", "bow", "launcher"},
    "armor": {"armor", "armour", "helmet", "shield", "accessory", "clothes"},
    "seed": {"seed", "seeds"},
    "egg": {"egg", "eggs"},
    "schematic": {"schematic", "blueprint", "recipe", "manual"},
    "valuable": {"valuable", "gold", "coin", "gem", "diamond", "ruby", "sapphire"},
}

FALLBACK_TERMS = {"misc", "other", "overflow", "everything", "general"}
MAX_MOVES = 96


def _words(value: str) -> set[str]:
    spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", value)
    return set(re.findall(r"[a-z0-9]+", spaced.lower()))


def _category_matches(words: set[str]) -> set[str]:
    return {
        category
        for category, terms in CATEGORY_TERMS.items()
        if words.intersection(terms)
    }


def _deterministic_routes(
    containers: list[StorageContainerSnapshot],
) -> dict[str, tuple[str, str, str]]:
    labeled = [container for container in containers if container.label.strip()]
    item_names: dict[str, str] = {}
    for container in containers:
        for item in container.items:
            item_names.setdefault(item.item_id, item.display_name or item.item_id)

    routes: dict[str, tuple[str, str, str]] = {}
    for item_id, display_name in item_names.items():
        item_words = _words(f"{item_id} {display_name}")
        item_categories = _category_matches(item_words)
        scored: list[tuple[int, StorageContainerSnapshot]] = []
        for container in labeled:
            label_words = _words(container.label)
            score = len(item_words.intersection(label_words)) * 20
            score += len(item_categories.intersection(_category_matches(label_words))) * 8
            if label_words.intersection(FALLBACK_TERMS):
                score += 1
            if score:
                scored.append((score, container))
        scored.sort(key=lambda pair: (-pair[0], pair[1].container_id))
        if not scored or (len(scored) > 1 and scored[0][0] == scored[1][0]):
            continue
        score, target = scored[0]
        confidence = "high" if score >= 8 else "medium"
        routes[item_id] = (
            target.container_id,
            confidence,
            f"Matches chest label '{target.label}'.",
        )
    return routes


def _parse_llm_routes(
    text: str,
    item_ids: set[str],
    targets: dict[str, StorageContainerSnapshot],
) -> dict[str, tuple[str, str, str]]:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return {}
    try:
        payload = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}

    routes: dict[str, tuple[str, str, str]] = {}
    for route in payload.get("routes", []):
        if not isinstance(route, dict):
            continue
        item_id = str(route.get("item_id", ""))
        target_id = str(route.get("target_container_id", ""))
        confidence = str(route.get("confidence", "")).lower()
        if item_id not in item_ids or target_id not in targets:
            continue
        if confidence not in {"high", "medium"}:
            continue
        reason = str(route.get("reason") or "Matched by the local storage planner.")[:120]
        routes[item_id] = (target_id, confidence, reason)
    return routes


class StorageOrganizer:
    def __init__(self, ollama: OllamaClient):
        self.ollama = ollama

    async def plan(self, snapshot: StorageSnapshotRequest) -> StoragePlan:
        containers = snapshot.containers
        labeled = {
            container.container_id: container
            for container in containers
            if container.label.strip()
        }
        item_ids = {
            item.item_id
            for container in containers
            for item in container.items
        }
        warnings: list[str] = []
        if not labeled:
            return self._empty_plan(
                snapshot,
                "No labeled chests were loaded.",
                ["Give destination chests names in Palworld, then scan again."],
            )

        deterministic = _deterministic_routes(containers)
        routes: dict[str, tuple[str, str, str]] = {}
        planner = "deterministic"
        prompt = json.dumps(
            {
                "chests": [
                    {
                        "container_id": container.container_id,
                        "label": container.label,
                    }
                    for container in labeled.values()
                ],
                "items": sorted(item_ids),
            },
            separators=(",", ":"),
        )
        try:
            llm_text = await self.ollama.chat(STORAGE_SYSTEM_PROMPT, prompt)
            routes = _parse_llm_routes(llm_text, item_ids, labeled)
            if routes:
                planner = "local-llm"
        except (httpx.HTTPError, KeyError, OSError, ValueError):
            warnings.append("The local LLM was unavailable; label rules were used.")

        for item_id, route in deterministic.items():
            routes.setdefault(item_id, route)

        moves: list[StorageMove] = []
        unmapped: set[str] = set()
        cross_base_routes = 0
        for container in containers:
            if not container.label.strip():
                continue
            for item in container.items:
                route = routes.get(item.item_id)
                if not route:
                    unmapped.add(item.display_name or item.item_id)
                    continue
                target_id, confidence, reason = route
                if target_id == container.container_id:
                    continue
                target = labeled[target_id]
                if target.base_id != container.base_id:
                    unmapped.add(item.display_name or item.item_id)
                    cross_base_routes += 1
                    continue
                moves.append(
                    StorageMove(
                        source_container_id=container.container_id,
                        source_slot=item.slot_index,
                        item_id=item.item_id,
                        display_name=item.display_name or item.item_id,
                        count=item.count,
                        target_container_id=target_id,
                        target_label=target.label,
                        reason=reason,
                        confidence=confidence,
                    )
                )

        if len(moves) > MAX_MOVES:
            moves = moves[:MAX_MOVES]
            warnings.append(f"The preview was limited to {MAX_MOVES} stack moves.")
        unlabeled_count = sum(1 for container in containers if not container.label.strip())
        if unlabeled_count:
            warnings.append(
                f"{unlabeled_count} unlabeled chest"
                f"{' was' if unlabeled_count == 1 else 's were'} ignored."
            )
        if cross_base_routes:
            warnings.append(
                f"{cross_base_routes} cross-base route"
                f"{' was' if cross_base_routes == 1 else 's were'} blocked."
            )

        fingerprint = hashlib.sha256(
            snapshot.model_dump_json().encode("utf-8")
        ).hexdigest()[:16]
        target_counts: dict[str, int] = defaultdict(int)
        for move in moves:
            target_counts[move.target_label] += 1
        target_summary = ", ".join(
            f"{label}: {count}" for label, count in sorted(target_counts.items())
        )
        summary = (
            f"{len(moves)} stack move{'s' if len(moves) != 1 else ''} planned"
            + (f" ({target_summary})." if target_summary else ".")
        )
        return StoragePlan(
            plan_id=fingerprint,
            summary=summary,
            planner=planner,
            moves=moves,
            unmapped_items=sorted(unmapped),
            warnings=warnings,
            can_execute=bool(moves),
        )

    @staticmethod
    def _empty_plan(
        snapshot: StorageSnapshotRequest,
        summary: str,
        warnings: list[str],
    ) -> StoragePlan:
        fingerprint = hashlib.sha256(
            snapshot.model_dump_json().encode("utf-8")
        ).hexdigest()[:16]
        return StoragePlan(
            plan_id=fingerprint,
            summary=summary,
            planner="deterministic",
            moves=[],
            unmapped_items=[],
            warnings=warnings,
            can_execute=False,
        )
