from fastapi import FastAPI, HTTPException

from .config import Settings
from .models import Answer, AskRequest
from .rag import Companion

settings = Settings()
companion = Companion(settings)
app = FastAPI(title="Palworld Local LLM Companion", version="0.1.0")


@app.get("/health")
async def health() -> dict[str, str | int | bool]:
    return {
        "status": "ok",
        "ollama": await companion.ollama.health(),
        "indexed_documents": companion.store.count(),
    }


@app.post("/ask", response_model=Answer)
async def ask(request: AskRequest) -> Answer:
    try:
        return await companion.ask(
            request.question,
            allow_web=request.allow_web,
            include_live=request.include_live,
        )
    except Exception as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
