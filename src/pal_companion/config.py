from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ollama_url: str = "http://localhost:11434"
    ollama_chat_model: str = "qwen2.5:14b"
    ollama_embed_model: str = "embeddinggemma"
    ollama_context_length: int = 8192
    ollama_keep_alive: str = "30m"

    palworld_rest_url: str = ""
    palworld_admin_password: str = ""
    brave_search_api_key: str = ""
    discord_token: str = ""
    discord_guild_id: int | None = None

    index_path: Path = Path("data/index/companion.sqlite3")
    retrieval_limit: int = 4
    retrieval_min_score: float = 0.35
    answer_cache_ttl_seconds: int = 604800
    answer_cache_web_ttl_seconds: int = 3600
    answer_cache_live_ttl_seconds: int = 15
