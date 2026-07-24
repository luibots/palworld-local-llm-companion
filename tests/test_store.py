from pathlib import Path

import pytest

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
