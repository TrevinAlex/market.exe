"""Application settings loaded from environment / .env file."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    sectors_api_key: str = "your-sectors-api-key-here"
    sectors_base_url: str = "https://api.sectors.app/v2"
    cache_ttl_seconds: int = 900

    allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000"
    rate_limit_requests: int = 60
    rate_limit_window_seconds: int = 60
    debug: bool = False

    app_password: str = ""
    auth_secret: str = ""
    auth_token_ttl_seconds: int = 43200
    login_max_failures: int = 5
    login_window_seconds: int = 300

    users_db_path: str = "users.db"

    supabase_url: str = ""
    supabase_service_key: str = ""
    max_pins: int = 20

    @property
    def origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


settings = Settings()
