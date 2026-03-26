from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
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
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
    ]
    max_sql_rows: int = 100
    graph_max_initial_nodes: int = 200
    graph_push_threshold: int = 200

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value):
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return []
            if value.startswith("["):
                return value
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @property
    def database_dir(self) -> str:
        return os.path.dirname(self.database_path) or "."


@lru_cache()
def get_settings() -> Settings:
    return Settings()
