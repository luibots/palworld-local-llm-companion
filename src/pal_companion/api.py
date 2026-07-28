import secrets
from pathlib import Path

import httpx
from fastapi import Cookie, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import Settings
from .models import (
    Answer,
    AskRequest,
    RarePalTarget,
    ShareVendorRequest,
    StoragePlan,
    StorageSnapshotRequest,
    VendorLocation,
    VoiceRequest,
    WelcomeMessage,
    WelcomeMessageRequest,
)
from .rag import Companion
from .storage import StorageOrganizer
from .transcription import ConfirmationTranscriber
from .vendors import find_vendor, list_rare_targets, list_vendors, queue_vendor_share
from .voice import NeuralVoice
from .welcome import WelcomeMessageService

settings = Settings()
companion = Companion(settings)
neural_voice = NeuralVoice(settings.voice_cache_path)
confirmation_transcriber = ConfirmationTranscriber()
welcome_message_service = WelcomeMessageService(companion.store)
storage_organizer = StorageOrganizer(companion.ollama)
app = FastAPI(title="Palworld Local LLM Companion", version="0.3.1")
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
        "cached_answers": companion.store.cached_answer_count(),
        "cached_audio": neural_voice.cached_audio_count(),
        "voice_engine": "edge-neural",
        "speech_engine": "windows-sapi-grammar",
        "web_search_configured": bool(settings.brave_search_api_key),
        "live_context_configured": bool(
            settings.palworld_rest_url and settings.palworld_admin_password
        ),
        "welcome_message_service": True,
        "storage_organizer": True,
    }


@app.post("/internal/welcome-message", response_model=WelcomeMessage)
async def construct_welcome_message(
    welcome_request: WelcomeMessageRequest,
    request: Request,
) -> WelcomeMessage:
    client_host = request.client.host if request.client else ""
    if client_host not in {"127.0.0.1", "::1", "testclient"}:
        raise HTTPException(status_code=403, detail="This endpoint is local only.")
    return welcome_message_service.construct(welcome_request)


@app.get("/vendors", response_model=list[VendorLocation])
async def vendors(
    player_name: str | None = None,
    pal_companion_session: str | None = Cookie(default=None),
) -> list[VendorLocation]:
    if not secrets.compare_digest(pal_companion_session or "", session_token):
        raise HTTPException(status_code=403, detail="Open the companion UI to start a session.")
    try:
        origin = await companion.palworld.player_position(player_name)
    except (httpx.HTTPError, TypeError, ValueError):
        origin = None
    return list_vendors(origin)


@app.get("/rare-targets", response_model=list[RarePalTarget])
async def rare_targets(
    pal_companion_session: str | None = Cookie(default=None),
) -> list[RarePalTarget]:
    if not secrets.compare_digest(pal_companion_session or "", session_token):
        raise HTTPException(status_code=403, detail="Open the companion UI to start a session.")
    return list_rare_targets()


@app.post("/storage/plan", response_model=StoragePlan)
async def plan_storage(
    snapshot: StorageSnapshotRequest,
    pal_companion_session: str | None = Cookie(default=None),
) -> StoragePlan:
    if not secrets.compare_digest(pal_companion_session or "", session_token):
        raise HTTPException(status_code=403, detail="Open the companion UI to start a session.")
    return await storage_organizer.plan(snapshot)


@app.post("/guild/share-vendor")
async def share_vendor(
    request: ShareVendorRequest,
    pal_companion_session: str | None = Cookie(default=None),
) -> dict[str, str]:
    if not secrets.compare_digest(pal_companion_session or "", session_token):
        raise HTTPException(status_code=403, detail="Open the companion UI to start a session.")
    vendor = find_vendor(request.vendor_id)
    if vendor is None:
        raise HTTPException(status_code=404, detail="Unknown vendor.")
    try:
        queue_vendor_share(vendor, request.player_name)
    except OSError as error:
        raise HTTPException(status_code=503, detail="Could not queue the Discord post.") from error
    return {"status": "queued", "vendor_id": vendor.vendor_id}


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
            player_name=request.player_name,
            player_level=request.player_level,
        )
    except Exception as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@app.post("/voice")
async def voice(
    request: VoiceRequest,
    pal_companion_session: str | None = Cookie(default=None),
) -> FileResponse:
    if not secrets.compare_digest(pal_companion_session or "", session_token):
        raise HTTPException(status_code=403, detail="Open the companion UI to start a session.")
    try:
        audio_path = await neural_voice.synthesize(request.text, request.voice)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    return FileResponse(audio_path, media_type="audio/mpeg")


@app.post("/transcribe-confirmation")
async def transcribe_confirmation(
    request: Request,
    pal_companion_session: str | None = Cookie(default=None),
) -> dict[str, str]:
    if not secrets.compare_digest(pal_companion_session or "", session_token):
        raise HTTPException(status_code=403, detail="Open the companion UI to start a session.")
    if request.headers.get("content-type", "").split(";")[0] != "audio/wav":
        raise HTTPException(status_code=415, detail="A WAV microphone recording is required.")
    wav_bytes = await request.body()
    if len(wav_bytes) > 2_000_000:
        raise HTTPException(status_code=413, detail="The microphone recording is too large.")
    try:
        transcript = await confirmation_transcriber.transcribe(wav_bytes)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    return {"transcript": transcript}


@app.post("/listen-confirmation")
async def listen_confirmation(
    pal_companion_session: str | None = Cookie(default=None),
) -> dict[str, str]:
    if not secrets.compare_digest(pal_companion_session or "", session_token):
        raise HTTPException(status_code=403, detail="Open the companion UI to start a session.")
    try:
        transcript = await confirmation_transcriber.listen()
    except Exception as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    return {"transcript": transcript}
