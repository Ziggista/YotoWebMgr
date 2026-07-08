from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "YotoWebMgr"
    environment: str = "development"
    database_url: str = "postgresql+psycopg://yotowebmgr:change-me@localhost:5432/yotowebmgr"
    processed_path: str = "/var/lib/yotowebmgr/media/processed"
    artwork_path: str = "/var/lib/yotowebmgr/media/artwork"


@lru_cache
def get_settings() -> Settings:
    return Settings()
