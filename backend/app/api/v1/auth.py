import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from jwt import PyJWTError as JWTError
from sqlalchemy.orm import Session

from app.core.clerk import create_demo_sign_in_ticket
from app.core.config import settings
from app.core.limiter import limiter
from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, RefreshRequest, TokenResponse, UserResponse
from app.services.auth_service import authenticate_user, create_tokens, refresh_access_token

router = APIRouter()

def _require_local_login():
    if not settings.ALLOW_LOCAL_JWT:
        raise HTTPException(status_code=404, detail="Password sign-in is disabled. Sign in with Clerk.")


@router.get("/config")
def auth_config():
    """Public: tells the frontend which sign-in options exist."""
    return {"provider": "clerk", "demo_enabled": bool(settings.DEMO_ENABLED and settings.CLERK_SECRET_KEY)}


@router.post("/demo")
@limiter.limit("10/minute")
def demo_ticket(request: Request):
    """Public: one-time Clerk sign-in ticket for the shared read-only demo account."""
    if not (settings.DEMO_ENABLED and settings.CLERK_SECRET_KEY):
        raise HTTPException(status_code=404, detail="Demo access is not enabled")
    try:
        return {"ticket": create_demo_sign_in_ticket()}
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="Could not start a demo session. Try again shortly.")


@router.post("/login", response_model=TokenResponse)
def login(credentials: LoginRequest, db: Session = Depends(get_db), _=Depends(_require_local_login)):
    user = authenticate_user(db, credentials.email, credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    return create_tokens(user)


@router.post("/login/form", response_model=TokenResponse)
def login_form(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db), _=Depends(_require_local_login)):
    """OAuth2 form-compatible login endpoint."""
    user = authenticate_user(db, form.username, form.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    return create_tokens(user)


@router.post("/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest, db: Session = Depends(get_db), _=Depends(_require_local_login)):
    try:
        return refresh_access_token(body.refresh_token, db=db)
    except HTTPException:
        raise
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse(
        id=str(current_user.id),
        org_id=str(current_user.org_id),
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
        is_active=current_user.is_active,
        is_demo=current_user.email == settings.DEMO_EMAIL,
        org_name=current_user.organization.name if current_user.organization else None,
    )
