"""Application settings loaded from environment / .env file."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    sectors_api_key: str = "your-sectors-api-key-here"
    sectors_base_url: str = "https://api.sectors.app/v2"
    cache_ttl_seconds: int = 900

    # --- security ---------------------------------------------------------
    # Comma-separated allowed CORS origins. Default to local dev hosts; set
    # ALLOWED_ORIGINS in .env for a deployed demo. "*" is accepted but warned.
    allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000"
    # Simple fixed-window rate limit per client IP.
    rate_limit_requests: int = 60       # requests ...
    rate_limit_window_seconds: int = 60  # ... per this window
    # Debug mode echoes upstream error details; keep False for demos.
    debug: bool = False

    @property
    def origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


settings = Settings()
