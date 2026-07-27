from typing import Literal

from pydantic import BaseModel, Field


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
