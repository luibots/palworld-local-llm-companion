import asyncio
import hashlib
from pathlib import Path

import edge_tts

VOICE_NAMES = {
    "emma": "en-US-EmmaMultilingualNeural",
    "andrew": "en-US-AndrewMultilingualNeural",
    "ava": "en-US-AvaMultilingualNeural",
    "brian": "en-US-BrianMultilingualNeural",
    "roger": "en-US-RogerNeural",
}


class NeuralVoice:
    def __init__(self, cache_path: Path):
        self.cache_path = cache_path
        self.cache_path.mkdir(parents=True, exist_ok=True)
        self._locks: dict[str, asyncio.Lock] = {}

    async def synthesize(self, text: str, voice: str) -> Path:
        voice_name = VOICE_NAMES.get(voice)
        if not voice_name:
            raise ValueError(f"Unknown voice: {voice}")

        cache_key = hashlib.sha256(
            f"edge-neural-v1\0{voice_name}\0{text}".encode()
        ).hexdigest()
        output_path = self.cache_path / f"{cache_key}.mp3"
        if output_path.exists():
            return output_path

        lock = self._locks.setdefault(cache_key, asyncio.Lock())
        async with lock:
            if output_path.exists():
                return output_path

            communicate = edge_tts.Communicate(
                text,
                voice_name,
                rate="-3%",
                volume="+0%",
            )
            audio = bytearray()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio.extend(chunk["data"])
            if not audio:
                raise RuntimeError("The neural voice service returned no audio.")

            await asyncio.to_thread(output_path.write_bytes, audio)
            return output_path

    def cached_audio_count(self) -> int:
        return sum(1 for _ in self.cache_path.glob("*.mp3"))
