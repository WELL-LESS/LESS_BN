from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "well less API"
    app_env: str = "development"
    api_v1_prefix: str = "/api/v1"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    supabase_url: str | None = None
    supabase_project_ref: str | None = None
    supabase_publishable_key: str | None = None
    supabase_secret_key: str | None = None
    openai_api_key: str | None = None
    openai_model: str = "gpt-5.6-luna"
    openai_prompt_id: str | None = None
    openai_prompt_version: str | None = None
    openai_response_schema_version: str = "suitability-analysis-v1"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def has_supabase_config(self) -> bool:
        return bool(self.supabase_url and self.supabase_secret_key)

    @property
    def has_openai_config(self) -> bool:
        return bool(self.openai_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
