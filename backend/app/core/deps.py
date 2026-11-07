from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core import clerk
from app.core.config import settings
from app.core.database import get_db
from app.core.security import verify_token
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
# Writes a read-only viewer may still make: they draft text, they do not change records.
VIEWER_WRITE_ALLOWLIST = ("/api/v1/reminders/draft", "/api/v1/ml/predict")


def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if creds is None or not creds.credentials:
        raise credentials_exception
    token = creds.credentials

    user: User | None = None
    if clerk.is_clerk_token(token):
        try:
            claims = clerk.verify_session_token(token)
            user = clerk.get_or_provision_user(db, claims["sub"])
        except clerk.ClerkAuthError as e:
            raise HTTPException(status_code=401, detail=str(e), headers={"WWW-Authenticate": "Bearer"})
        if not user.is_active:
            raise credentials_exception
    elif settings.ALLOW_LOCAL_JWT:
        try:
            payload = verify_token(token, token_type="access")
        except JWTError:
            raise credentials_exception
        user = db.query(User).filter(User.id == payload.get("sub"), User.is_active == True).first()  # noqa: E712
    if user is None:
        raise credentials_exception

    # Viewers (including the public demo) are strictly read-only.
    if (
        user.role == "viewer"
        and request.method not in SAFE_METHODS
        and not request.url.path.startswith(VIEWER_WRITE_ALLOWLIST)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Read-only access: viewers cannot change records.",
        )
    if user.organization and not user.organization.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Organization is inactive",
        )
    return user


def require_roles(*roles: str | list[str]):
    """Dependency factory that enforces role-based access."""
    flat_roles: list[str] = []
    for r in roles:
        if isinstance(r, (list, tuple, set)):
            flat_roles.extend(r)
        else:
            flat_roles.append(r)

    def _checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in flat_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {', '.join(flat_roles)}",
            )
        return current_user
    return _checker


require_role = require_roles


def get_org_id(current_user: User = Depends(get_current_user)) -> str:
    """Returns the authenticated user's org_id as a string."""
    return str(current_user.org_id)
