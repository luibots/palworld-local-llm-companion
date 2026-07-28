import httpx
import pytest
from pydantic import ValidationError

from pal_companion.models import (
    StorageContainerSnapshot,
    StorageItemStack,
    StorageSnapshotRequest,
)
from pal_companion.storage import StorageOrganizer

PLAYER_ID = "1" * 32


class FakeOllama:
    def __init__(self, response: str = "", fail: bool = False):
        self.response = response
        self.fail = fail

    async def chat(self, system: str, prompt: str) -> str:
        assert "Return JSON only" in system
        assert '"chests"' in prompt
        if self.fail:
            raise httpx.ConnectError("offline")
        return self.response


def container(
    container_id: str,
    label: str,
    *items: StorageItemStack,
) -> StorageContainerSnapshot:
    return StorageContainerSnapshot(
        container_id=container_id * 32,
        model_id=("f" if container_id != "f" else "e") * 32,
        base_id="b" * 32,
        owner_player_id=PLAYER_ID,
        label=label,
        items=list(items),
    )


@pytest.mark.asyncio
async def test_llm_routes_only_valid_ids() -> None:
    source = container(
        "a",
        "Inbox",
        StorageItemStack(item_id="Coal", slot_index=2, count=80),
    )
    target = container("c", "Ore and coal")
    response = (
        '{"routes":[{"item_id":"Coal","target_container_id":"'
        + target.container_id
        + '","confidence":"high","reason":"Coal belongs with mined resources."},'
        '{"item_id":"Invented","target_container_id":"'
        + target.container_id
        + '","confidence":"high","reason":"invalid"}]}'
    )
    plan = await StorageOrganizer(FakeOllama(response)).plan(
        StorageSnapshotRequest(player_id=PLAYER_ID, containers=[source, target])
    )

    assert plan.planner == "local-llm"
    assert plan.can_execute
    assert len(plan.moves) == 1
    assert plan.moves[0].source_slot == 2
    assert plan.moves[0].target_container_id == target.container_id


@pytest.mark.asyncio
async def test_label_rules_are_safe_fallback() -> None:
    source = container(
        "a",
        "Unsorted",
        StorageItemStack(
            item_id="PalMetalIngot",
            display_name="Pal Metal Ingot",
            slot_index=4,
            count=12,
        ),
    )
    target = container("c", "Ore and ingots")
    plan = await StorageOrganizer(FakeOllama(fail=True)).plan(
        StorageSnapshotRequest(player_id=PLAYER_ID, containers=[source, target])
    )

    assert plan.planner == "deterministic"
    assert len(plan.moves) == 1
    assert plan.moves[0].target_label == "Ore and ingots"
    assert "LLM was unavailable" in plan.warnings[0]


@pytest.mark.asyncio
async def test_items_already_in_target_are_not_moved() -> None:
    target = container(
        "c",
        "Coal",
        StorageItemStack(item_id="Coal", slot_index=0, count=50),
    )
    plan = await StorageOrganizer(FakeOllama("{}")).plan(
        StorageSnapshotRequest(player_id=PLAYER_ID, containers=[target])
    )

    assert not plan.can_execute
    assert plan.moves == []


@pytest.mark.asyncio
async def test_unlabeled_chests_are_outside_organizer_scope() -> None:
    source = container(
        "a",
        "",
        StorageItemStack(
            item_id="Coal",
            display_name="Coal",
            slot_index=0,
            count=9,
        ),
    )
    target = container("c", "Ore and coal")
    plan = await StorageOrganizer(FakeOllama(fail=True)).plan(
        StorageSnapshotRequest(player_id=PLAYER_ID, containers=[source, target])
    )

    assert not plan.moves
    assert "1 unlabeled chest was ignored." in plan.warnings


def test_other_players_chests_are_rejected_by_contract() -> None:
    foreign = container("a", "Ore")
    foreign.owner_player_id = "2" * 32

    with pytest.raises(ValidationError, match="current player's chests"):
        StorageSnapshotRequest(player_id=PLAYER_ID, containers=[foreign])
