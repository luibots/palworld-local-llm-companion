import asyncio
import subprocess
import tempfile
from pathlib import Path


class ConfirmationTranscriber:
    def __init__(self) -> None:
        self.script_path = (
            Path(__file__).with_name("scripts") / "Listen-MarkerConfirmation.ps1"
        )
        self._listen_lock = asyncio.Lock()

    async def listen(self, duration_seconds: float = 4.0) -> str:
        async with self._listen_lock:
            return await self._recognize(
                "-TimeoutSeconds",
                str(max(1, min(10, round(duration_seconds)))),
            )

    async def transcribe(self, wav_bytes: bytes) -> str:
        if not wav_bytes:
            raise ValueError("The microphone recording was empty.")
        async with self._listen_lock:
            path: Path | None = None
            try:
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as wav_file:
                    wav_file.write(wav_bytes)
                    path = Path(wav_file.name)
                return await self._recognize("-WavePath", str(path))
            finally:
                if path:
                    path.unlink(missing_ok=True)

    async def _recognize(self, *arguments: str) -> str:
        if not self.script_path.is_file():
            raise RuntimeError("The Windows speech confirmation helper is missing.")
        creation_flags = (
            subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
        )
        process = await asyncio.create_subprocess_exec(
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(self.script_path),
            *arguments,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            creationflags=creation_flags,
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            message = stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(message or "Windows speech confirmation failed.")
        return _normalize_transcript(stdout.decode("utf-8", errors="replace"))


def _normalize_transcript(text: str) -> str:
    return " ".join(text.strip().strip("[]").split())
