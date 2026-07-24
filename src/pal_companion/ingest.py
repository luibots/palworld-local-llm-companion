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


async def ingest_jsonl(
    path: Path,
    store: VectorStore,
    ollama: OllamaClient,
    batch_size: int = 64,
    replace_prefix: str | None = None,
) -> int:
    documents = read_jsonl(path)
    if replace_prefix and any(
        not document.source_id.startswith(replace_prefix) for document in documents
    ):
        raise ValueError(f"all source IDs must start with replacement prefix {replace_prefix!r}")
    indexed = 0
    for start in range(0, len(documents), batch_size):
        batch = documents[start : start + batch_size]
        embeddings = await ollama.embed(
            [f"{document.title}\n{document.text}" for document in batch]
        )
        indexed += store.upsert(batch, embeddings)
    if replace_prefix:
        store.delete_stale_prefix(
            replace_prefix,
            {document.source_id for document in documents},
        )
    return indexed
