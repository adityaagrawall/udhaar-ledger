"""Udhaar Ledger FastAPI application."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import logging

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.v1.router import router as api_v1_router
from app.core.limiter import limiter
from app.core.migrations import apply_schema_upgrades
from app.core.security_middleware import MaxBodySizeMiddleware, SecurityHeadersMiddleware
from app.core.config import settings
from app.core.database import engine
from app.models.base import Base
# Import all models so metadata knows all tables
import app.models  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure all tables are created on startup
    Base.metadata.create_all(bind=engine)
    # No Alembic migrations exist yet; see app/core/migrations.py.
    apply_schema_upgrades(engine)
    yield


logger = logging.getLogger("udhaar.api")
_docs_on = settings.ENVIRONMENT != "production" or settings.ENABLE_DOCS

app = FastAPI(
    title="Udhaar Ledger API",
    description="Receivables & Credit Intelligence Platform for Indian Distributors & Wholesalers",
    version="1.0.0",
    docs_url="/docs" if _docs_on else None,
    redoc_url="/redoc" if _docs_on else None,
    openapi_url="/openapi.json" if _docs_on else None,
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Never leak stack traces or internals to clients; log them server-side."""
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# CORS Middleware
# NOTE: allow_credentials=True is incompatible with allow_origins=["*"] in browsers.
# Since the frontend uses Bearer tokens (not cookies), credentials mode is not needed.
_ALLOWED_ORIGINS = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    max_age=600,
)
app.add_middleware(MaxBodySizeMiddleware)
app.add_middleware(SecurityHeadersMiddleware)  # outermost: headers on every response, including errors

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
