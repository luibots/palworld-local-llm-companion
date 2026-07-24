import httpx


class OllamaClient:
    def __init__(self, base_url: str, chat_model: str, embed_model: str):
        self.base_url = base_url.rstrip("/")
        self.chat_model = chat_model
        self.embed_model = embed_model

    async def embed(self, inputs: list[str]) -> list[list[float]]:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{self.base_url}/api/embed",
                json={"model": self.embed_model, "input": inputs},
            )
            response.raise_for_status()
            return response.json()["embeddings"]

    async def chat(self, system: str, prompt: str) -> str:
        async with httpx.AsyncClient(timeout=180) as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.chat_model,
                    "stream": False,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                    "options": {"temperature": 0.15},
                },
            )
            response.raise_for_status()
            return response.json()["message"]["content"].strip()

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.is_success
        except httpx.HTTPError:
            return False
