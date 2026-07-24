import json
import math
import sqlite3
from pathlib import Path

from .models import RetrievedSource, SourceDocument


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


class VectorStore:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    source_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    text TEXT NOT NULL,
                    url TEXT,
                    kind TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    embedding TEXT NOT NULL
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def upsert(self, documents: list[SourceDocument], embeddings: list[list[float]]) -> int:
        if len(documents) != len(embeddings):
            raise ValueError("documents and embeddings must have equal lengths")
        rows = [
            (
                document.source_id,
                document.title,
                document.text,
                document.url,
                document.kind,
                json.dumps(document.metadata, separators=(",", ":")),
                json.dumps(embedding, separators=(",", ":")),
            )
            for document, embedding in zip(documents, embeddings, strict=True)
        ]
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO documents
                    (source_id, title, text, url, kind, metadata, embedding)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id) DO UPDATE SET
                    title=excluded.title,
                    text=excluded.text,
                    url=excluded.url,
                    kind=excluded.kind,
                    metadata=excluded.metadata,
                    embedding=excluded.embedding
                """,
                rows,
            )
        return len(rows)

    def search(self, query_embedding: list[float], limit: int = 6) -> list[RetrievedSource]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT source_id, title, text, url, kind, metadata, embedding FROM documents"
            ).fetchall()
        results = [
            RetrievedSource(
                source_id=row[0],
                title=row[1],
                text=row[2],
                url=row[3],
                kind=row[4],
                metadata=json.loads(row[5]),
                score=cosine_similarity(query_embedding, json.loads(row[6])),
            )
            for row in rows
        ]
        return sorted(results, key=lambda item: item.score, reverse=True)[:limit]

    def count(self) -> int:
        with self._connect() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0])
