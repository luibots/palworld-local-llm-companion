from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pal_companion.api import app
from pal_companion.config import Settings
from pal_companion.game_data import _clean_text, representative_locations
from pal_companion.models import Answer, RetrievedSource, SourceDocument
from pal_companion.palworld import PalworldClient, _current_player, world_to_map
from pal_companion.rag import (
    _answer_cache_key,
    _extract_map_markers,
    _level_route_context,
    _normalize_output,
    _rerank_local,
    _split_answer_output,
)
from pal_companion.store import VectorStore, cosine_similarity
from pal_companion.voice import NeuralVoice


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

    deleted = store.delete_stale_prefix("p", {"pal-current"})
    assert deleted == 1
    assert store.count() == 1


def test_answer_cache_persists_and_index_updates_invalidate_it(tmp_path: Path) -> None:
    store = VectorStore(tmp_path / "index.sqlite3")
    answer = Answer(
        text="Coal is here.",
        spoken_summary="Coal is nearby.",
        confidence="high",
        sources=[],
    )
    store.put_cached_answer("coal", answer)

    cached = store.get_cached_answer("coal", max_age_seconds=60)
    assert cached is not None
    assert cached.cached is True
    assert cached.spoken_summary == "Coal is nearby."
    assert store.cached_answer_count() == 1

    document = SourceDocument(source_id="coal", title="Coal", text="New location")
    store.upsert([document], [[1.0, 0.0]])
    assert store.get_cached_answer("coal", max_age_seconds=60) is None
    assert store.cached_answer_count() == 0


def test_world_coordinates_match_pal_command_calibration() -> None:
    map_x, map_y = world_to_map(-353_000, 273_000)
    assert map_x == pytest.approx(250.0)
    assert map_y == pytest.approx(-500.0)


def test_ui_issues_session_cookie_and_protects_ask() -> None:
    with TestClient(app) as client:
        page = client.get("/")
        assert page.status_code == 200
        assert "pal_companion_session" in page.cookies
        health = client.get("/health")
        assert "web_search_configured" in health.json()
        assert "live_context_configured" in health.json()
        assert health.json()["voice_engine"] == "edge-neural"

    with TestClient(app) as client:
        denied = client.post(
            "/ask",
            json={"question": "Where is coal?", "allow_web": False, "include_live": False},
        )
        assert denied.status_code == 403
        denied_voice = client.post("/voice", json={"text": "Hello", "voice": "emma"})
        assert denied_voice.status_code == 403


@pytest.mark.asyncio
async def test_neural_voice_rejects_unknown_alias(tmp_path: Path) -> None:
    voice = NeuralVoice(tmp_path)
    with pytest.raises(ValueError, match="Unknown voice"):
        await voice.synthesize("Hello", "not-a-voice")


def test_game_data_text_cleanup_and_location_sampling() -> None:
    assert _clean_text("<itemName id=|Coal|/> found\r\nhere") == "Coal found here"

    locations = [(float(index), 0.0, 1, 3) for index in range(20)]
    selected = representative_locations(locations, limit=4)
    assert len(selected) == 4
    assert len(set(selected)) == 4


def test_location_reranking_prefers_exact_coordinate_guide() -> None:
    sources = [
        RetrievedSource(
            source_id="game:item:Coal",
            title="Coal",
            text="A generic item description without a route.",
            score=0.8,
        ),
        RetrievedSource(
            source_id="guide:coal",
            title="Coal farming locations",
            text="Mine five nodes at (-233, -365).",
            kind="guide",
            score=0.5,
        ),
    ]
    ranked = _rerank_local("Where can I find coal?", sources)
    assert ranked[0].source_id == "guide:coal"
    assert _normalize_output("**Coal** [source_id: game:item:Coal]") == ("Coal [game:item:Coal]")


def test_answer_coordinates_become_structured_map_markers() -> None:
    sources = [
        RetrievedSource(
            source_id="guide:coal",
            title="Coal farming locations",
            text="Mine coal at (-233, -365).",
            kind="guide",
        )
    ]
    markers = _extract_map_markers(
        "- Mount Obsidian at (-233, -365). [guide:coal]\n"
        "- Desert camp near (189.5, -39). [guide:coal]\n"
        "- Duplicate (-233, -365). [guide:coal]",
        sources,
    )

    assert [(marker.x, marker.y) for marker in markers] == [
        (-233.0, -365.0),
        (189.5, -39.0),
    ]
    assert markers[0].label == "Mount Obsidian"
    assert markers[0].source_id == "guide:coal"
    assert markers[0].icon == "resource"


def test_map_marker_icons_follow_location_context() -> None:
    markers = _extract_map_markers(
        "- Alpha Pal boss at (10, 20).\n"
        "- Forgotten dungeon at (30, 40).\n"
        "- Wandering merchant at (50, 60).",
        [],
    )

    assert [marker.icon for marker in markers] == ["boss", "dungeon", "person"]


def test_ambiguous_marker_inherits_answer_subject_icon() -> None:
    markers = _extract_map_markers(
        "Coal locations:\n- Mount Obsidian at (-233, -365).\n- Verdant Brook at (190, -41).",
        [],
    )

    assert [marker.icon for marker in markers] == ["resource", "resource"]


def test_answer_cache_key_normalizes_case_whitespace_and_punctuation() -> None:
    settings = Settings()
    first = _answer_cache_key(
        "  Where   IS coal? ",
        allow_web=False,
        include_live=False,
        settings=settings,
    )
    second = _answer_cache_key(
        "where is coal",
        allow_web=False,
        include_live=False,
        settings=settings,
    )
    assert first == second


def test_answer_cache_separates_player_levels() -> None:
    settings = Settings()
    low_level = _answer_cache_key(
        "Where is Foxcicle?",
        allow_web=False,
        include_live=True,
        player_name="Luis",
        player_level=12,
        settings=settings,
    )
    high_level = _answer_cache_key(
        "Where is Foxcicle?",
        allow_web=False,
        include_live=True,
        player_name="Luis",
        player_level=50,
        settings=settings,
    )
    assert low_level != high_level


@pytest.mark.asyncio
async def test_client_level_becomes_grounded_live_context() -> None:
    sources = await PalworldClient("", "").live_context(player_name="Luis", player_level=23)
    assert len(sources) == 1
    assert sources[0].source_id == "live:current-player"
    assert "Luis: level 23" in sources[0].text


def test_current_player_matches_name_or_only_online_player() -> None:
    players = [
        {"name": "Luis", "level": 23},
        {"name": "Aye", "level": 40},
    ]
    assert _current_player(players, "luis") == players[0]
    assert _current_player([players[1]], None) == players[1]


def test_level_route_context_selects_compatible_exact_entity_location() -> None:
    sources = [
        RetrievedSource(
            source_id="game:pal:IceFox",
            title="Foxcicle",
            text=(
                "Representative wild map coordinates: (-423, 495) levels 35-37, "
                "(244, 65) levels 30-34."
            ),
        ),
        RetrievedSource(
            source_id="game:pal:Kitsunebi",
            title="Foxparks",
            text="Representative wild map coordinates: (10, -441) levels 5-7.",
        ),
    ]
    context = _level_route_context("Where is Foxcicle?", sources, player_level=32)
    assert context is not None
    assert "BEST MATCH: Foxcicle at (244, 65)" in context.text
    assert "Status: LEVEL MATCH" in context.text
    assert "Foxparks" not in context.text


def test_level_route_context_flags_low_level_player() -> None:
    sources = [
        RetrievedSource(
            source_id="game:pal:IceFox",
            title="Foxcicle",
            text="Representative wild map coordinates: (244, 65) levels 30-34.",
        )
    ]
    context = _level_route_context("Where is Foxcicle?", sources, player_level=10)
    assert context is not None
    assert "Status: OVER YOUR LEVEL" in context.text
    assert "No verified level-compatible location exists" in context.text
    assert "20 levels above" in context.text
    assert "do not recommend any higher-level alternative" in context.text


def test_level_route_context_does_not_borrow_unrelated_pal_range() -> None:
    sources = [
        RetrievedSource(
            source_id="guide:coal",
            title="Coal farming locations",
            text="Mine coal at (-233, -365).",
            kind="guide",
        ),
        RetrievedSource(
            source_id="game:pal:Blazamut",
            title="Blazamut",
            text="Representative wild map coordinates: (-1981, 1621) levels 80-80.",
        ),
    ]
    context = _level_route_context("Where can I find coal?", sources, player_level=20)
    assert context is not None
    assert "level risk is unverified" in context.text
    assert "80-80" not in context.text


def test_spoken_summary_is_separated_and_cleaned_for_tts() -> None:
    answer, summary = _split_answer_output(
        "Coal Locations\n- Mine coal at (-233, -365). [guide:coal]\n"
        "SPOKEN_SUMMARY: Head to the Bamboo Groves at (-233, -365). [guide:coal]"
    )

    assert "SPOKEN_SUMMARY" not in answer
    assert "[guide:coal]" in answer
    assert summary == "Head to the Bamboo Groves at (-233, -365)."


def test_spoken_summary_falls_back_to_first_useful_points() -> None:
    _, summary = _split_answer_output(
        "Best route:\n- Mine the Bamboo Groves first. [guide:coal]\n"
        "- Bring a heat-resistant outfit. [guide:coal]\n"
        "- Return with a flying mount. [guide:coal]\n"
        "- This detail should not be read. [guide:coal]"
    )

    assert summary == (
        "Mine the Bamboo Groves first. Bring a heat-resistant outfit. "
        "Return with a flying mount."
    )
