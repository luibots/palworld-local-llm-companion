import asyncio
import io
from typing import Any

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly


class ConfirmationTranscriber:
    def __init__(self, model: str) -> None:
        self.model = model
        self._pipeline: Any | None = None
        self._load_lock = asyncio.Lock()
        self._listen_lock = asyncio.Lock()

    async def transcribe(self, wav_bytes: bytes) -> str:
        audio, _ = await asyncio.to_thread(self._decode_wav, wav_bytes)
        return await self._transcribe_audio(audio)

    async def listen(self, duration_seconds: float = 3.5) -> str:
        async with self._listen_lock:
            audio = await asyncio.to_thread(self._record_microphone, duration_seconds)
            return await self._transcribe_audio(audio)

    async def _transcribe_audio(self, audio: np.ndarray) -> str:
        pipeline = await self._get_pipeline()
        result = await asyncio.to_thread(
            pipeline,
            {"array": audio, "sampling_rate": 16000},
        )
        return _normalize_transcript(str(result.get("text", "")))

    async def _get_pipeline(self) -> Any:
        if self._pipeline is not None:
            return self._pipeline
        async with self._load_lock:
            if self._pipeline is None:
                self._pipeline = await asyncio.to_thread(self._load_pipeline)
        return self._pipeline

    def _load_pipeline(self) -> Any:
        import torch
        from transformers import pipeline

        device = 0 if torch.cuda.is_available() else -1
        dtype = torch.float16 if device == 0 else torch.float32
        return pipeline(
            "automatic-speech-recognition",
            model=self.model,
            device=device,
            dtype=dtype,
        )

    @staticmethod
    def _record_microphone(duration_seconds: float) -> np.ndarray:
        import sounddevice as sd

        frames = max(1, round(16000 * duration_seconds))
        recording = sd.rec(frames, samplerate=16000, channels=1, dtype="float32")
        sd.wait()
        return np.asarray(recording[:, 0], dtype=np.float32)

    @staticmethod
    def _decode_wav(wav_bytes: bytes) -> tuple[np.ndarray, int]:
        if not wav_bytes:
            raise ValueError("The microphone recording was empty.")
        audio, sample_rate = sf.read(
            io.BytesIO(wav_bytes),
            dtype="float32",
            always_2d=False,
        )
        if audio.ndim == 2:
            audio = audio.mean(axis=1)
        if not len(audio):
            raise ValueError("The microphone recording contained no audio.")
        if sample_rate != 16000:
            audio = resample_poly(audio, 16000, sample_rate).astype(np.float32)
            sample_rate = 16000
        return np.asarray(audio, dtype=np.float32), sample_rate


def _normalize_transcript(text: str) -> str:
    return " ".join(text.strip().strip("[]").split())
