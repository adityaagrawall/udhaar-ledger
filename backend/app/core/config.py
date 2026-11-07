from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+psycopg2://collectiq:collectiq@localhost:5432/collectiq"

    # Security
    SECRET_KEY: str = "change-me-in-production-minimum-32-chars-required"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # LLM
    LLM_PROVIDER: str = "openai"  # openai | anthropic | google
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "gpt-4o-mini"

    # Uploads
    UPLOAD_MAX_MB: int = 20

    # Rate limits
    RATE_LIMIT_REMINDER: str = "20/minute"

    # Environment
    ENVIRONMENT: str = "development"

    # Clerk authentication (the only sign-in method outside tests)
    CLERK_SECRET_KEY: str = ""
    CLERK_ISSUER: str = ""  # e.g. https://<your-instance>.clerk.accounts.dev
    CLERK_AUTHORIZED_PARTIES: str = "http://localhost:3000,http://localhost:3001"
    CLERK_API_URL: str = "https://api.clerk.com/v1"
    # Organisation that newly signed-in Clerk users join (slug). Empty = first organisation.
    DEFAULT_ORG_SLUG: str = ""
    # Comma-separated emails that are provisioned as admin; everyone else is a read-only viewer.
    ADMIN_EMAILS: str = ""

    # Public read-only demo for visitors (recruiters). Uses a Clerk sign-in ticket, no password.
    DEMO_ENABLED: bool = False
    DEMO_EXTERNAL_ID: str = "udhaar-demo-viewer"
    DEMO_EMAIL: str = "demo+viewer@udhaar-ledger.dev"

    # Legacy email/password JWTs. Off by default; the test suite turns it on.
    ALLOW_LOCAL_JWT: bool = False

    # --- Hardening ---
    ENABLE_DOCS: bool = False  # /docs and /openapi.json are hidden in production unless true
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_DEFAULT: str = "240/minute"  # per client IP, every route
    RATE_LIMIT_HEAVY: str = "10/minute"  # imports, training, exports
    MAX_REQUEST_BYTES: int = 25 * 1024 * 1024
    IMPORT_MAX_ROWS: int = 20000
    IMPORT_MAX_UNZIPPED_MB: int = 200  # zip-bomb guard for .xlsx
    # When false, only users that already exist locally (matched by email) can sign in.
    AUTO_PROVISION_USERS: bool = True

    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001"

    @property
    def authorized_parties(self) -> list[str]:
        return [p.strip() for p in self.CLERK_AUTHORIZED_PARTIES.split(",") if p.strip()]

    @property
    def admin_emails(self) -> set[str]:
        return {e.strip().lower() for e in self.ADMIN_EMAILS.split(",") if e.strip()}

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

_DEFAULT_SECRET = "change-me-in-production-minimum-32-chars-required"
if settings.ENVIRONMENT == "production":
    if settings.SECRET_KEY == _DEFAULT_SECRET or len(settings.SECRET_KEY) < 32:
        raise RuntimeError("SECRET_KEY must be set to a random value of 32+ characters in production")
    if not settings.CLERK_SECRET_KEY or not settings.CLERK_ISSUER:
        raise RuntimeError("CLERK_SECRET_KEY and CLERK_ISSUER are required in production")
    if settings.ALLOW_LOCAL_JWT:
        raise RuntimeError("ALLOW_LOCAL_JWT must be off in production")
