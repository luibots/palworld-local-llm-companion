import json
from pathlib import Path

from .models import SourceDocument
from .ollama import OllamaClient
from .store import VectorStore


def read_jsonl(path: Path) -> list[SourceDocument]:
    documents: list[SourceDocument] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        payload = json.loads(line)
        payload.setdefault("source_id", f"{path.stem}:{line_number}")
        documents.append(SourceDocument.model_validate(payload))
    return documents


async def ingest_jsonl(path: Path, store: VectorStore, ollama: OllamaClient) -> int:
    documents = read_jsonl(path)
    embeddings = await ollama.embed(
        [f"{document.title}\n{document.text}" for document in documents]
    )
    return store.upsert(documents, embeddings)
