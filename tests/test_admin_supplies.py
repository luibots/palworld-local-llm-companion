import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

import pal_companion.api as api_module
from pal_companion.admin_supplies import AdminSupplies, AdminSupplyError
from pal_companion.config import Settings
from pal_companion.models import SourceDocument
from pal_companion.store import VectorStore


def supply_settings(**overrides: object) -> Settings:
    values = {
        "admin_supplies_enabled": True,
        "paldefender_url": "http://paldefender.invalid:8213",
        "paldefender_token": "private-test-token",
        "admin_supply_player_id": "steam_test-player",
        "admin_supply_max_count": 5000,
    }
    values.update(overrides)
    return Settings(**values)


@pytest.mark.asyncio
async def test_admin_supply_grant_uses_fixed_player_and_scoped_token() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/pdapi/give/items/steam_test-player"
        assert request.headers["Authorization"] == "Bearer private-test-token"
        assert json.loads((await request.aread()).decode()) == {
            "Items": [{"ItemID": "Glass", "Count": 250}]
        }
        return httpx.Response(200, json={"Granted": {"Items": 250}})

    service = AdminSupplies(
        supply_settings(),
        transport=httpx.MockTransport(handler),
    )

    assert service.configured is True
    assert await service.grant("Glass", 250) == 250


@pytest.mark.asyncio
async def test_admin_supply_rejects_disabled_or_excessive_grants() -> None:
    disabled = AdminSupplies(supply_settings(admin_supplies_enabled=False))
    with pytest.raises(AdminSupplyError, match="not configured"):
        await disabled.grant("Glass", 1)

    enabled = AdminSupplies(supply_settings(admin_supply_max_count=100))
    with pytest.raises(AdminSupplyError, match="between 1 and 100"):
        await enabled.grant("Glass", 101)


def test_item_catalog_searches_names_and_internal_ids(tmp_path: Path) -> None:
    store = VectorStore(tmp_path / "index.sqlite3")
    documents = [
        SourceDocument(
            source_id="game:item:Glass",
            title="Glass",
            text="Glass is an item.",
            metadata={"internal_id": "Glass"},
        ),
        SourceDocument(
            source_id="game:item:Coal",
            title="Coal",
            text="Coal is an item.",
            metadata={"internal_id": "Coal"},
        ),
        SourceDocument(
            source_id="game:pal:CoalFox",
            title="Coal Fox",
            text="Not an item.",
            metadata={"internal_id": "CoalFox"},
        ),
    ]
    store.upsert(documents, [[1.0], [1.0], [1.0]])

    assert store.list_items("glas") == [("Glass", "Glass")]
    assert store.list_items("coal") == [("Coal", "Coal")]


def test_admin_supply_endpoint_is_session_and_game_client_protected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeSupplies:
        enabled = True
        configured = True
        max_count = 5000

        def __init__(self) -> None:
            self.calls: list[tuple[str, int]] = []

        async def grant(self, item_id: str, count: int) -> int:
            self.calls.append((item_id, count))
            return count

    fake = FakeSupplies()
    monkeypatch.setattr(api_module, "admin_supplies", fake)

    with TestClient(api_module.app) as client:
        denied_session = client.post(
            "/admin/supplies/grant",
            json={"item_id": "Glass", "count": 10, "confirmed": True},
            headers={"X-Pal-Companion-Client": "ue4ss"},
        )
        assert denied_session.status_code == 403

        client.get("/")
        denied_browser = client.post(
            "/admin/supplies/grant",
            json={"item_id": "Glass", "count": 10, "confirmed": True},
        )
        assert denied_browser.status_code == 403

        denied_confirmation = client.post(
            "/admin/supplies/grant",
            json={"item_id": "Glass", "count": 10, "confirmed": False},
            headers={"X-Pal-Companion-Client": "ue4ss"},
        )
        assert denied_confirmation.status_code == 409

        granted = client.post(
            "/admin/supplies/grant",
            json={"item_id": "Glass", "count": 10, "confirmed": True},
            headers={"X-Pal-Companion-Client": "ue4ss"},
        )

    assert granted.status_code == 200
    assert granted.json() == {
        "item_id": "Glass",
        "requested": 10,
        "granted": 10,
        "public_announcement": False,
    }
    assert fake.calls == [("Glass", 10)]
