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

    # --- admin authentication ---------------------------------------------
    # Viewing is public. Admin/edit routes need a bearer token obtained by
    # POSTing APP_PASSWORD to /api/admin/login. Empty = admin login disabled.
    app_password: str = ""
    # Signs tokens. Leave empty to use a random per-process secret (tokens are
    # then invalidated on every restart). Set it to keep logins across restarts.
    auth_secret: str = ""
    auth_token_ttl_seconds: int = 43200  # 12 hours
    # Brute-force guard: this many failed logins per IP per window -> 429.
    login_max_failures: int = 5
    login_window_seconds: int = 300

    # --- user accounts ----------------------------------------------------
    # SQLite file holding registered users (created automatically).
    users_db_path: str = "users.db"

    # --- user history (Supabase) -----------------------------------------
    # Project URL, e.g. https://xxxx.supabase.co, and the service_role key
    # (Settings -> API). Server-side only. Empty = history disabled.
    supabase_url: str = ""
    supabase_service_key: str = ""
    # Max pinned stocks per user. The PINNED view scores each one (4 Sectors
    # credits per stock, cached for CACHE_TTL_SECONDS), so keep this modest.
    max_pins: int = 20

    @property
    def origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


settings = Settings()
