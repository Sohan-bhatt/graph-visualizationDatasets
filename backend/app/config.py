from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
import os


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    gemini_api_key: str = ""
    openai_api_key: str = ""
    database_url: str = "sqlite+aiosqlite:///./data/o2c.db"
    database_path: str = "data/o2c.db"
    data_dir: str = "data/sap-o2c-data"
    upload_dir: str = "data/uploads"
    browse_base_dir: str = "data"
    # Stored as a raw string to avoid pydantic-settings trying to JSON-parse
    # a comma-separated URL list before validators run. Parsed by cors_origins_list.
    cors_origins: str = "http://localhost:3000,http://localhost:5173"
    max_sql_rows: int = 100
    graph_max_initial_nodes: int = 200
    graph_push_threshold: int = 200

    @property
    def cors_origins_list(self) -> list[str]:
        value = self.cors_origins.strip()
        if not value:
            return []
        return [item.strip() for item in value.split(",") if item.strip()]

    @property
    def database_dir(self) -> str:
        return os.path.dirname(self.database_path) or "."


@lru_cache()
def get_settings() -> Settings:
    return Settings()
