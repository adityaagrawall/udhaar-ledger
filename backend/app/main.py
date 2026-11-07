"""Udhaar Ledger FastAPI application."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import router as api_v1_router
from app.core.config import settings
from app.core.database import engine
from app.models.base import Base
# Import all models so metadata knows all tables
import app.models  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure all tables are created on startup
    Base.metadata.create_all(bind=engine)
    # No Alembic migrations exist yet; create_all never alters existing tables,
    # so add columns introduced after first deploy idempotently.
    from sqlalchemy import text
    with engine.begin() as conn:
        conn.execute(text(
            "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS is_disputed BOOLEAN NOT NULL DEFAULT FALSE"
        ))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS clerk_user_id VARCHAR(64)"))
        conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_users_clerk_user_id ON users (clerk_user_id)"
        ))
    yield


app = FastAPI(
    title="Udhaar Ledger API",
    description="Receivables & Credit Intelligence Platform for Indian Distributors & Wholesalers",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS Middleware
# NOTE: allow_credentials=True is incompatible with allow_origins=["*"] in browsers.
# Since the frontend uses Bearer tokens (not cookies), credentials mode is not needed.
_ALLOWED_ORIGINS = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API v1 router
app.include_router(api_v1_router)


@app.get("/health", tags=["health"])
def health_check():
    return {
        "status": "healthy",
        "service": "Udhaar Ledger Receivables Intelligence",
        "version": "1.0.0",
    }


@app.get("/", tags=["root"])
def root():
    return {
        "message": "Welcome to Udhaar Ledger API",
        "docs": "/docs",
        "health": "/health",
    }
