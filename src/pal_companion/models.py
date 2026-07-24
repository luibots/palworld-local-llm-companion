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


class Answer(BaseModel):
    text: str
    confidence: Literal["high", "medium", "low"]
    sources: list[RetrievedSource]
