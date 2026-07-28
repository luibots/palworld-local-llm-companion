from typing import Literal

from pydantic import BaseModel, Field, model_validator


class SourceDocument(BaseModel):
    source_id: str
    title: str
    text: str
    url: str | None = None
    kind: Literal["game-data", "guide", "web", "live"] = "game-data"
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class RetrievedSource(SourceDocument):
    score: float = 1.0


class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=1000)
    allow_web: bool = True
    include_live: bool = True
    player_name: str | None = Field(default=None, max_length=100)
    player_level: int | None = Field(default=None, ge=1, le=255)


class VoiceRequest(BaseModel):
    text: str = Field(min_length=1, max_length=6000)
    voice: str = "emma"


class WelcomeMessageRequest(BaseModel):
    player_key: str = Field(min_length=1, max_length=180)
    player_name: str = Field(min_length=1, max_length=100)
    world_day: int | None = Field(default=None, ge=0)
    online_players: list[str] = Field(default_factory=list, max_length=32)
    server_name: str | None = Field(default=None, max_length=100)


class WelcomeMessage(BaseModel):
    message: str = Field(min_length=1, max_length=240)
    returning_player: bool
    visit_number: int = Field(ge=1)
    constructed_by: Literal["context-service"] = "context-service"


class VendorStockPal(BaseModel):
    name: str
    base_price: int
    specialty: str


class VendorLocation(BaseModel):
    vendor_id: str
    name: str
    vendor_type: Literal["black-marketeer", "pal-merchant"]
    x: float
    y: float
    level: int | None = None
    fast_travel: str
    route: str
    stock_summary: str
    reliability: Literal["verified", "community"]
    underground: bool = False
    distance: float | None = None
    source_url: str | None = None
    stock_pool: str
    stock_level_min: int
    stock_level_max: int
    stock_highlights: list[VendorStockPal] = Field(default_factory=list)
    premium_stock: bool = False


class ShareVendorRequest(BaseModel):
    vendor_id: str = Field(min_length=2, max_length=80)
    player_name: str | None = Field(default=None, max_length=100)


class MapMarker(BaseModel):
    label: str
    x: float
    y: float
    source_id: str | None = None
    icon: Literal[
        "pin",
        "star",
        "box",
        "resource",
        "pal",
        "food",
        "boss",
        "base",
        "fruit",
        "dungeon",
        "egg",
        "person",
        "book",
        "flower",
    ] = "pin"


class RarePalTarget(BaseModel):
    target_id: str
    name: str
    internal_id: str
    rarity: int
    base_price: int
    specialty: str
    level_min: int
    level_max: int
    locations: list[MapMarker]
    vendor_pool: str
    vendor_note: str


class Answer(BaseModel):
    text: str
    spoken_summary: str | None = None
    confidence: Literal["high", "medium", "low"]
    sources: list[RetrievedSource]
    coordinates: list[MapMarker] = Field(default_factory=list)
    cached: bool = False


class StorageItemStack(BaseModel):
    item_id: str = Field(min_length=1, max_length=120)
    display_name: str | None = Field(default=None, max_length=160)
    slot_index: int = Field(ge=0, le=255)
    count: int = Field(ge=1, le=999_999)


class StorageContainerSnapshot(BaseModel):
    container_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    model_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    base_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    owner_player_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    label: str = Field(default="", max_length=80)
    x: float | None = None
    y: float | None = None
    z: float | None = None
    items: list[StorageItemStack] = Field(default_factory=list, max_length=128)


class StorageSnapshotRequest(BaseModel):
    player_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    excluded_container_count: int = Field(default=0, ge=0, le=4096)
    containers: list[StorageContainerSnapshot] = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def containers_belong_to_player(self) -> "StorageSnapshotRequest":
        if any(
            container.owner_player_id != self.player_id
            for container in self.containers
        ):
            raise ValueError("Storage snapshots may contain only the current player's chests.")
        return self


class StorageMove(BaseModel):
    source_container_id: str
    source_slot: int
    item_id: str
    display_name: str
    count: int
    target_container_id: str
    target_label: str
    reason: str
    confidence: Literal["high", "medium"]


class StoragePlan(BaseModel):
    plan_id: str
    summary: str
    planner: Literal["local-llm", "deterministic"]
    moves: list[StorageMove]
    unmapped_items: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    can_execute: bool = False
