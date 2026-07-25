import json
import math
import os
import re
from datetime import UTC, datetime
from pathlib import Path

from .models import MapMarker, RarePalTarget, VendorLocation, VendorStockPal

SOURCE_URL = "https://drawpie.com/blog/palworld-1-0-black-marketeer-locations/"

EARLY_STOCK = [
    VendorStockPal(name="Warsect", base_price=2913, specialty="MINING / DEFENSE"),
    VendorStockPal(name="Mammorest", base_price=2220, specialty="LUMBERING / TANK"),
    VendorStockPal(name="Helzephyr", base_price=2109, specialty="FLYING / TRANSPORT"),
]

PREMIUM_STOCK = [
    VendorStockPal(name="Relaxaurus Lux", base_price=2685, specialty="ELECTRIC / ATTACK"),
    VendorStockPal(name="Sekhmet", base_price=2638, specialty="HANDIWORK 6"),
    VendorStockPal(name="Menasting", base_price=2469, specialty="MINING 5 / DEFENSE"),
]

RARE_TARGETS = (
    RarePalTarget(
        target_id="lunaris",
        name="Lunaris",
        internal_id="Mutant",
        rarity=6,
        base_price=1845,
        specialty="HANDIWORK 4 / CARRY CAPACITY",
        level_min=25,
        level_max=29,
        locations=[
            MapMarker(label="Lunaris hunt", x=83, y=-698, icon="pal"),
            MapMarker(label="Lunaris hunt", x=-411, y=-614, icon="pal"),
        ],
        vendor_pool="Dark_04",
        vendor_note="Possible Dark_04 roll; no verified Dark_04 broker placement is mapped yet.",
    ),
)

VENDORS = (
    VendorLocation(
        vendor_id="desolate-church",
        name="Desolate Church Broker",
        vendor_type="black-marketeer",
        x=41,
        y=-403,
        level=43,
        fast_travel="Desolate Church",
        route="Drop west from the church and enter the Abandoned Mineshaft.",
        stock_summary="Five random Pals from the Dark_01 pool; refreshes about every 48 minutes.",
        reliability="verified",
        underground=True,
        source_url=SOURCE_URL,
        stock_pool="Dark_01",
        stock_level_min=20,
        stock_level_max=30,
        stock_highlights=EARLY_STOCK,
    ),
    VendorLocation(
        vendor_id="eastern-wild-island",
        name="Eastern Wild Island Broker",
        vendor_type="black-marketeer",
        x=460,
        y=-125,
        level=45,
        fast_travel="Eastern Wild Island",
        route="Travel west from the waypoint to the ring of rocks.",
        stock_summary="Five random Pals from the Dark_01 pool; open-world placement may vary by world load.",
        reliability="verified",
        underground=False,
        source_url=SOURCE_URL,
        stock_pool="Dark_01",
        stock_level_min=20,
        stock_level_max=30,
        stock_highlights=EARLY_STOCK,
    ),
    VendorLocation(
        vendor_id="cove-mineshaft",
        name="Cove Mineshaft Broker",
        vendor_type="black-marketeer",
        x=-293,
        y=-186,
        level=47,
        fast_travel="Sealed Realm of the Winged Tyrant",
        route="Head west toward the bridge and enter the mineshaft beneath it.",
        stock_summary="Five random Pals from the Dark_01 pool; refreshes about every 48 minutes.",
        reliability="verified",
        underground=True,
        source_url=SOURCE_URL,
        stock_pool="Dark_01",
        stock_level_min=20,
        stock_level_max=30,
        stock_highlights=EARLY_STOCK,
    ),
    VendorLocation(
        vendor_id="barren-mountains",
        name="Barren Mountains Broker",
        vendor_type="black-marketeer",
        x=525,
        y=333,
        level=54,
        fast_travel="PIDF Tower Entrance",
        route="Move west from the tower and descend through the cave opening.",
        stock_summary="Five random Pals from the stronger Dark_03 pool; refreshes about every 48 minutes.",
        reliability="verified",
        underground=True,
        source_url=SOURCE_URL,
        stock_pool="Dark_03",
        stock_level_min=42,
        stock_level_max=48,
        stock_highlights=PREMIUM_STOCK,
        premium_stock=True,
    ),
)


def list_vendors(origin: tuple[float, float] | None = None) -> list[VendorLocation]:
    locations = []
    for vendor in VENDORS:
        distance = None
        if origin is not None:
            distance = round(math.dist(origin, (vendor.x, vendor.y)))
        locations.append(vendor.model_copy(update={"distance": distance}))
    return sorted(
        locations,
        key=lambda vendor: (
            vendor.distance is None,
            vendor.distance if vendor.distance is not None else vendor.level or 999,
        ),
    )


def find_vendor(vendor_id: str) -> VendorLocation | None:
    return next((vendor for vendor in VENDORS if vendor.vendor_id == vendor_id), None)


def list_rare_targets() -> list[RarePalTarget]:
    return list(RARE_TARGETS)


def queue_vendor_share(vendor: VendorLocation, player_name: str | None) -> Path:
    app_data = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    queue_path = app_data / "com.luibots.palcommand" / "auto" / "discord-events.jsonl"
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    requested_by = re.sub(r"[^A-Za-z0-9 _.-]", "", player_name or "").strip()[:40]
    event = {
        "event_type": "guild_location",
        "location_type": "vendor",
        "vendor_id": vendor.vendor_id,
        "name": vendor.name,
        "vendor_type": vendor.vendor_type,
        "x": vendor.x,
        "y": vendor.y,
        "level": vendor.level,
        "fast_travel": vendor.fast_travel,
        "route": vendor.route,
        "requested_by": requested_by or "Guild member",
        "source": "PAL COMPANION",
        "occurred_at": datetime.now(UTC).isoformat(),
    }
    with queue_path.open("a", encoding="utf-8") as queue:
        queue.write(json.dumps(event, separators=(",", ":")) + "\n")
    return queue_path
