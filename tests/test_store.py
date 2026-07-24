from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pal_companion.api import app
from pal_companion.models import SourceDocument
from pal_companion.palworld import world_to_map
from pal_companion.store import VectorStore, cosine_similarity


def test_cosine_similarity() -> None:
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_store_returns_closest_document(tmp_path: Path) -> None:
    store = VectorStore(tmp_path / "index.sqlite3")
    documents = [
        SourceDocument(source_id="coal", title="Coal", text="Coal location"),
        SourceDocument(source_id="pal", title="Pal", text="Pal location"),
    ]
    store.upsert(documents, [[1.0, 0.0], [0.0, 1.0]])
    assert store.search([0.9, 0.1], limit=1)[0].source_id == "coal"


def test_world_coordinates_match_pal_command_calibration() -> None:
    map_x, map_y = world_to_map(-353_000, 273_000)
    assert map_x == pytest.approx(250.0)
    assert map_y == pytest.approx(-500.0)


def test_ui_issues_session_cookie_and_protects_ask() -> None:
    with TestClient(app) as client:
        page = client.get("/")
        assert page.status_code == 200
        assert "pal_companion_session" in page.cookies

    with TestClient(app) as client:
        denied = client.post(
            "/ask",
            json={"question": "Where is coal?", "allow_web": False, "include_live": False},
        )
        assert denied.status_code == 403
