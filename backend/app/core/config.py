from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "YotoWebMgr API"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "postgresql+psycopg://yotowebmgr:change-me@localhost:5432/yotowebmgr"
    reset_database_on_start: bool = False
    import_drop_path: str = "/var/lib/yotowebmgr/media/imports/drop"
    browser_upload_path: str = "/var/lib/yotowebmgr/media/imports/uploads"
    artwork_path: str = "/var/lib/yotowebmgr/media/artwork"
    yoto_token_store_mode: str = "kubernetes_secret"
    yoto_token_secret_name: str = "yotowebmgr-secrets"
    yoto_token_secret_namespace: str = "yotowebmgr"


@lru_cache
def get_settings() -> Settings:
    return Settings()
