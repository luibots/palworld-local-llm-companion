import secrets
from pathlib import Path

from fastapi import Cookie, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import Settings
from .models import Answer, AskRequest
from .rag import Companion

settings = Settings()
companion = Companion(settings)
app = FastAPI(title="Palworld Local LLM Companion", version="0.1.0")
web_root = Path(__file__).with_name("ui")
session_token = secrets.token_urlsafe(32)
app.mount("/assets", StaticFiles(directory=web_root / "assets"), name="assets")


@app.get("/", include_in_schema=False)
async def companion_ui() -> FileResponse:
    response = FileResponse(web_root / "index.html")
    response.set_cookie(
        "pal_companion_session",
        session_token,
        httponly=True,
        samesite="strict",
        secure=False,
    )
    return response


@app.get("/health")
async def health() -> dict[str, str | int | bool]:
    return {
        "status": "ok",
        "ollama": await companion.ollama.health(),
        "indexed_documents": companion.store.count(),
        "web_search_configured": bool(settings.brave_search_api_key),
        "live_context_configured": bool(
            settings.palworld_rest_url and settings.palworld_admin_password
        ),
    }


@app.post("/ask", response_model=Answer)
async def ask(
    request: AskRequest,
    pal_companion_session: str | None = Cookie(default=None),
) -> Answer:
    if not secrets.compare_digest(pal_companion_session or "", session_token):
        raise HTTPException(status_code=403, detail="Open the companion UI to start a session.")
    try:
        return await companion.ask(
            request.question,
            allow_web=request.allow_web,
            include_live=request.include_live,
        )
    except Exception as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
