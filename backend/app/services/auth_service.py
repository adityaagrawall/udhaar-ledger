"""
Auth service: login, token creation.
"""

from sqlalchemy.orm import Session

from app.core.security import create_access_token, create_refresh_token, verify_password, verify_token
from app.models.user import User


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = db.query(User).filter(User.email == email.lower().strip(), User.is_active == True).first()
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def create_tokens(user: User) -> dict:
    payload = {"sub": str(user.id), "org_id": str(user.org_id), "role": user.role}
    return {
        "access_token": create_access_token(payload),
        "refresh_token": create_refresh_token(payload),
        "token_type": "bearer",
    }


from fastapi import HTTPException
from sqlalchemy.orm import Session

def refresh_access_token(refresh_token: str, db: Session | None = None) -> dict:
    payload = verify_token(refresh_token, token_type="refresh")
    user_id = payload.get("sub")
    if db is not None:
        user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
        if user is None:
            raise HTTPException(status_code=401, detail="User account is inactive or not found")
        if user.organization and not user.organization.is_active:
            raise HTTPException(status_code=401, detail="Organization is inactive")
        role = user.role
        org_id = str(user.org_id)
    else:
        role = payload["role"]
        org_id = payload["org_id"]

    new_payload = {"sub": user_id, "org_id": org_id, "role": role}
    return {
        "access_token": create_access_token(new_payload),
        "refresh_token": create_refresh_token(new_payload),
        "token_type": "bearer",
    }
