import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from .models import SourceDocument
from .palworld import world_to_map

WORK_LABELS = {
    "EmitFlame": "Kindling",
    "Watering": "Watering",
    "Seeding": "Planting",
    "GenerateElectricity": "Electricity",
    "Handcraft": "Handiwork",
    "Collection": "Gathering",
    "Deforest": "Lumbering",
    "Mining": "Mining",
    "OilExtraction": "Oil Extraction",
    "ProductMedicine": "Medicine",
    "Cool": "Cooling",
    "Transport": "Transporting",
    "MonsterFarm": "Farming",
}


def _rows(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    try:
        return payload["Exports"][0]["Table"]["Data"]
    except (KeyError, IndexError, TypeError) as error:
        raise ValueError(f"{path.name} is not a converted Unreal DataTable") from error


def _fields(row: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["Name"]: item for item in row.get("Value", []) if item.get("Name")}


def _value(fields: dict[str, dict[str, Any]], name: str, default: Any = None) -> Any:
    item = fields.get(name)
    return item.get("Value", default) if item else default


def _clean_text(value: str | None) -> str:
    if not value:
        return ""
    value = re.sub(r"<itemName id=\|([^|]+)\|/>", r"\1", value)
    value = re.sub(r"<[^>]+>", " ", value)
    return " ".join(value.replace("\r", " ").replace("\n", " ").split())


def _text_map(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for row in _rows(path):
        text_property = _fields(row).get("TextData")
        if not text_property:
            continue
        text = _clean_text(text_property.get("CultureInvariantString"))
        if text:
            result[row["Name"]] = text
    return result


def _location(fields: dict[str, dict[str, Any]]) -> tuple[float, float] | None:
    values = _value(fields, "Location", [])
    if not values or not isinstance(values, list):
        return None
    vector = values[0].get("Value")
    if not isinstance(vector, dict) or "X" not in vector or "Y" not in vector:
        return None
    return world_to_map(float(vector["X"]), float(vector["Y"]))


def representative_locations(
    locations: list[tuple[float, float, int, int]],
    limit: int = 8,
) -> list[tuple[float, float, int, int]]:
    unique = {
        (round(x, 1), round(y, 1), level_min, level_max)
        for x, y, level_min, level_max in locations
    }
    candidates = sorted(unique)
    if len(candidates) <= limit:
        return candidates

    center_x = sum(point[0] for point in candidates) / len(candidates)
    center_y = sum(point[1] for point in candidates) / len(candidates)
    selected = [
        min(
            candidates,
            key=lambda point: (point[0] - center_x) ** 2 + (point[1] - center_y) ** 2,
        )
    ]
    remaining = set(candidates) - set(selected)
    while remaining and len(selected) < limit:
        next_point = max(
            remaining,
            key=lambda point: min(
                (point[0] - chosen[0]) ** 2 + (point[1] - chosen[1]) ** 2
                for chosen in selected
            ),
        )
        selected.append(next_point)
        remaining.remove(next_point)
    return sorted(selected)


def _item_maps(
    tables_dir: Path,
) -> tuple[dict[str, str], dict[str, str], dict[str, list[dict[str, Any]]]]:
    names = _text_map(tables_dir / "DT_ItemNameText_Common.json")
    descriptions = _text_map(tables_dir / "DT_ItemDescriptionText_Common.json")
    recipes: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in _rows(tables_dir / "DT_ItemRecipeDataTable.json"):
        fields = _fields(row)
        product_id = _value(fields, "Product_Id")
        if product_id:
            recipes[str(product_id)].append(fields)
    return names, descriptions, recipes


def _item_name(item_names: dict[str, str], item_id: str) -> str:
    return item_names.get(f"ITEM_NAME_{item_id}", item_id)


def _drop_maps(
    tables_dir: Path,
) -> tuple[dict[str, list[tuple[str, float, int, int]]], dict[str, set[str]]]:
    by_pal: dict[str, list[tuple[str, float, int, int]]] = defaultdict(list)
    by_item: dict[str, set[str]] = defaultdict(set)
    for row in _rows(tables_dir / "DT_PalDropItem.json"):
        fields = _fields(row)
        pal_id = _value(fields, "CharacterID")
        if not pal_id:
            continue
        for index in range(1, 11):
            item_id = _value(fields, f"ItemId{index}")
            if not item_id:
                continue
            drop = (
                str(item_id),
                float(_value(fields, f"Rate{index}", 0)),
                int(_value(fields, f"min{index}", 0)),
                int(_value(fields, f"Max{index}", 0)),
            )
            by_pal[str(pal_id)].append(drop)
            by_item[str(item_id)].add(str(pal_id))
    return by_pal, by_item


def _spawn_locations(
    tables_dir: Path,
) -> dict[str, list[tuple[float, float, int, int]]]:
    spawner_pals: dict[str, list[tuple[str, int, int]]] = defaultdict(list)
    for row in _rows(tables_dir / "DT_PalWildSpawner.json"):
        fields = _fields(row)
        if _value(fields, "SpawnerType") != "Common":
            continue
        spawner_name = _value(fields, "SpawnerName")
        if not spawner_name:
            continue
        for index in range(1, 11):
            pal_id = _value(fields, f"Pal_{index}")
            if pal_id:
                spawner_pals[str(spawner_name)].append(
                    (
                        str(pal_id),
                        int(_value(fields, f"LvMin_{index}", 0)),
                        int(_value(fields, f"LvMax_{index}", 0)),
                    )
                )

    result: dict[str, list[tuple[float, float, int, int]]] = defaultdict(list)
    for row in _rows(tables_dir / "DT_PalSpawnerPlacement.json"):
        fields = _fields(row)
        if _value(fields, "WorldName") != "PL_MainWorld5":
            continue
        spawner_name = _value(fields, "SpawnerName")
        location = _location(fields)
        if not spawner_name or not location:
            continue
        for pal_id, level_min, level_max in spawner_pals.get(str(spawner_name), []):
            result[pal_id].append((*location, level_min, level_max))
    return result


def _pal_documents(
    tables_dir: Path,
    item_names: dict[str, str],
    drops_by_pal: dict[str, list[tuple[str, float, int, int]]],
    spawn_locations: dict[str, list[tuple[float, float, int, int]]],
    game_build: str,
) -> tuple[list[SourceDocument], dict[str, str]]:
    pal_names = _text_map(tables_dir / "DT_PalNameText_Common.json")
    descriptions = _text_map(tables_dir / "DT_PalLongDescriptionText.json")
    documents: list[SourceDocument] = []
    display_names: dict[str, str] = {}

    for row in _rows(tables_dir / "DT_PalMonsterParameter.json"):
        fields = _fields(row)
        tribe = str(_value(fields, "Tribe", ""))
        if (
            not _value(fields, "IsPal", False)
            or int(_value(fields, "ZukanIndex", -1)) < 0
            or row["Name"] != tribe
        ):
            continue

        name_key = _value(fields, "OverrideNameTextID") or f"PAL_NAME_{tribe}"
        display_name = pal_names.get(str(name_key), tribe)
        display_names[tribe] = display_name
        elements = [
            str(element)
            for element in (
                _value(fields, "ElementType1"),
                _value(fields, "ElementType2"),
            )
            if element and element != "None"
        ]
        work = [
            f"{label} {int(_value(fields, f'WorkSuitability_{field}', 0))}"
            for field, label in WORK_LABELS.items()
            if int(_value(fields, f"WorkSuitability_{field}", 0)) > 0
        ]
        lines = [
            f"{display_name} is Paldeck #{int(_value(fields, 'ZukanIndex'))}.",
            f"Internal Pal ID: {tribe}.",
            f"Element: {', '.join(elements) or 'None listed'}.",
            (
                "Base stats: "
                f"HP {int(_value(fields, 'Hp', 0))}, "
                f"attack {int(_value(fields, 'ShotAttack', 0))}, "
                f"defense {int(_value(fields, 'Defense', 0))}, "
                f"stamina {int(_value(fields, 'Stamina', 0))}."
            ),
            f"Work suitability: {', '.join(work) if work else 'none listed'}.",
        ]
        description = descriptions.get(f"PAL_LONG_DESC_{tribe}")
        if description:
            lines.append(f"Paldeck description: {description}")

        drops = drops_by_pal.get(tribe, [])
        if drops:
            drop_text = ", ".join(
                (
                    f"{_item_name(item_names, item_id)} "
                    f"(rate {rate:g}, amount {minimum}-{maximum})"
                )
                for item_id, rate, minimum, maximum in drops[:12]
            )
            lines.append(f"Drop table entries: {drop_text}.")

        locations = representative_locations(spawn_locations.get(tribe, []))
        if locations:
            location_text = ", ".join(
                f"({x:.0f}, {y:.0f}) levels {level_min}-{level_max}"
                for x, y, level_min, level_max in locations
            )
            lines.append(f"Representative wild map coordinates: {location_text}.")

        documents.append(
            SourceDocument(
                source_id=f"game:pal:{tribe}",
                title=display_name,
                text="\n".join(lines),
                kind="game-data",
                metadata={
                    "game_build": game_build,
                    "internal_id": tribe,
                    "table": "DT_PalMonsterParameter",
                },
            )
        )
    return documents, display_names


def _item_documents(
    tables_dir: Path,
    item_names: dict[str, str],
    item_descriptions: dict[str, str],
    recipes: dict[str, list[dict[str, Any]]],
    drops_by_item: dict[str, set[str]],
    pal_names: dict[str, str],
    game_build: str,
) -> list[SourceDocument]:
    documents: list[SourceDocument] = []
    for row in _rows(tables_dir / "DT_ItemDataTable.json"):
        item_id = row["Name"]
        fields = _fields(row)
        name_key = _value(fields, "OverrideName") or f"ITEM_NAME_{item_id}"
        display_name = item_names.get(str(name_key))
        if not display_name:
            continue

        lines = [
            f"{display_name} is a Palworld item.",
            f"Internal item ID: {item_id}.",
            (
                f"Category: {_value(fields, 'TypeA', 'Unknown')} / "
                f"{_value(fields, 'TypeB', 'Unknown')}."
            ),
            (
                f"Rarity {int(_value(fields, 'Rarity', 0))}; "
                f"weight {float(_value(fields, 'Weight', 0)):g}; "
                f"maximum stack {int(_value(fields, 'MaxStackCount', 0))}; "
                f"base price {int(_value(fields, 'Price', 0))}."
            ),
        ]
        description_key = _value(fields, "OverrideDescription") or f"ITEM_DESC_{item_id}"
        description = item_descriptions.get(str(description_key))
        if description:
            lines.append(f"Description: {description}")

        item_recipes = recipes.get(item_id, [])
        for recipe in item_recipes[:3]:
            materials = []
            for index in range(1, 11):
                material_id = _value(recipe, f"Material{index}_Id")
                count = int(_value(recipe, f"Material{index}_Count", 0))
                if material_id and count:
                    materials.append(
                        f"{count} {_item_name(item_names, str(material_id))}"
                    )
            if materials:
                product_count = int(_value(recipe, "Product_Count", 1))
                lines.append(
                    f"Recipe for {product_count}: {', '.join(materials)}; "
                    f"work amount {int(_value(recipe, 'WorkAmount', 0))}."
                )

        dropped_by = sorted(
            pal_names[pal_id]
            for pal_id in drops_by_item.get(item_id, set())
            if pal_id in pal_names
        )
        if dropped_by:
            lines.append(f"Appears in drop tables for: {', '.join(dropped_by[:20])}.")

        documents.append(
            SourceDocument(
                source_id=f"game:item:{item_id}",
                title=display_name,
                text="\n".join(lines),
                kind="game-data",
                metadata={
                    "game_build": game_build,
                    "internal_id": item_id,
                    "table": "DT_ItemDataTable",
                },
            )
        )
    return documents


def build_game_documents(tables_dir: Path, game_build: str = "unknown") -> list[SourceDocument]:
    item_names, item_descriptions, recipes = _item_maps(tables_dir)
    drops_by_pal, drops_by_item = _drop_maps(tables_dir)
    locations = _spawn_locations(tables_dir)
    pals, pal_names = _pal_documents(
        tables_dir,
        item_names,
        drops_by_pal,
        locations,
        game_build,
    )
    items = _item_documents(
        tables_dir,
        item_names,
        item_descriptions,
        recipes,
        drops_by_item,
        pal_names,
        game_build,
    )
    return sorted([*pals, *items], key=lambda document: document.source_id)


def write_jsonl(documents: list[SourceDocument], output: Path) -> int:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="\n") as handle:
        for document in documents:
            handle.write(document.model_dump_json(exclude_none=True))
            handle.write("\n")
    return len(documents)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build private RAG documents from Palworld tables")
    parser.add_argument("--tables-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--game-build", default="unknown")
    args = parser.parse_args()
    count = write_jsonl(build_game_documents(args.tables_dir, args.game_build), args.output)
    print(f"Wrote {count} private game-data documents to {args.output}.")


if __name__ == "__main__":
    main()
