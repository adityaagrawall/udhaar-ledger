"""
Clerk session verification and user provisioning.

Flow: the frontend obtains a short-lived Clerk session JWT (RS256) and sends it as a
Bearer token. We verify its signature against the instance JWKS, its issuer, expiry and
authorised party, then map the Clerk user to a local User row (creating it on first use).
"""
from __future__ import annotations

import secrets
import threading
import time
from typing import Any, Optional

import httpx
import jwt
from jwt import PyJWTError as JWTError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.models.organization import Organization
from app.models.user import User, UserRole

_JWKS_TTL = 3600
_jwks_cache: dict[str, Any] = {"keys": None, "fetched": 0.0}
_lock = threading.Lock()


class ClerkAuthError(Exception):
    pass


def _clerk_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {settings.CLERK_SECRET_KEY}"}


def _get_jwks(force: bool = False) -> list[dict]:
    with _lock:
        fresh = time.time() - _jwks_cache["fetched"] < _JWKS_TTL
        if _jwks_cache["keys"] and fresh and not force:
            return _jwks_cache["keys"]
    resp = httpx.get(f"{settings.CLERK_ISSUER.rstrip('/')}/.well-known/jwks.json", timeout=10)
    resp.raise_for_status()
    keys = resp.json()["keys"]
    with _lock:
        _jwks_cache.update(keys=keys, fetched=time.time())
    return keys


def is_clerk_token(token: str) -> bool:
    try:
        return jwt.get_unverified_header(token).get("alg") == "RS256"
    except JWTError:
        return False


def verify_session_token(token: str) -> dict[str, Any]:
    if not settings.CLERK_ISSUER:
        raise ClerkAuthError("Clerk is not configured")
    try:
        kid = jwt.get_unverified_header(token).get("kid")
    except JWTError as e:
        raise ClerkAuthError("Malformed token") from e

    jwk = next((k for k in _get_jwks() if k.get("kid") == kid), None)
    if jwk is None:  # key rotation: refresh once
        jwk = next((k for k in _get_jwks(force=True) if k.get("kid") == kid), None)
    if jwk is None:
        raise ClerkAuthError("Unknown signing key")

    try:
        claims = jwt.decode(
            token,
            jwt.PyJWK(jwk).key,
            algorithms=["RS256"],  # never accept the token's own alg choice
            issuer=settings.CLERK_ISSUER.rstrip("/"),
            leeway=10,
            options={"verify_aud": False, "require": ["exp", "iat", "sub", "iss"]},
        )
    except JWTError as e:
        raise ClerkAuthError("Invalid or expired session") from e

    azp = claims.get("azp")
    if azp and settings.authorized_parties and azp not in settings.authorized_parties:
        raise ClerkAuthError("Token issued for an unauthorised origin")
    if not claims.get("sub"):
        raise ClerkAuthError("Token has no subject")
    return claims


def _fetch_clerk_user(clerk_user_id: str) -> dict[str, Any]:
    resp = httpx.get(f"{settings.CLERK_API_URL}/users/{clerk_user_id}", headers=_clerk_headers(), timeout=10)
    resp.raise_for_status()
    return resp.json()


def _primary_email(u: dict[str, Any]) -> str:
    primary = u.get("primary_email_address_id")
    for e in u.get("email_addresses", []):
        if e.get("id") == primary:
            return e["email_address"].lower()
    emails = u.get("email_addresses") or []
    return emails[0]["email_address"].lower() if emails else f"{u['id']}@users.clerk"


def _default_org(db: Session) -> Organization:
    q = db.query(Organization).filter(Organization.is_active == True)  # noqa: E712
    org = q.filter(Organization.slug == settings.DEFAULT_ORG_SLUG).first() if settings.DEFAULT_ORG_SLUG else None
    org = org or q.order_by(Organization.created_at.asc()).first()
    if org is None:
        raise ClerkAuthError("No organisation exists to join. Seed the database first.")
    return org


def get_or_provision_user(db: Session, clerk_user_id: str) -> User:
    user = db.query(User).filter(User.clerk_user_id == clerk_user_id).first()
    if user is not None:
        return user

    info = _fetch_clerk_user(clerk_user_id)
    email = _primary_email(info)
    is_demo = info.get("external_id") == settings.DEMO_EXTERNAL_ID
    name = " ".join(p for p in [info.get("first_name"), info.get("last_name")] if p) or (
        "Demo Visitor" if is_demo else email.split("@")[0]
    )

    # Link an existing local account with the same email (e.g. a seeded admin)
    user = db.query(User).filter(User.email == email, User.clerk_user_id == None).first()  # noqa: E711
    if user is not None and not is_demo:
        user.clerk_user_id = clerk_user_id
        db.commit()
        return user

    if not settings.AUTO_PROVISION_USERS and not is_demo and email not in settings.admin_emails:
        raise ClerkAuthError("This account has not been invited")

    role = UserRole.admin.value if (email in settings.admin_emails and not is_demo) else UserRole.viewer.value
    user = User(
        org_id=_default_org(db).id,
        email=email,
        full_name=name,
        role=role,
        is_active=True,
        clerk_user_id=clerk_user_id,
        hashed_password=hash_password(secrets.token_urlsafe(32)),  # unusable: sign-in is via Clerk only
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# --- Demo access ------------------------------------------------------------
def _find_or_create_demo_user() -> str:
    r = httpx.get(
        f"{settings.CLERK_API_URL}/users",
        params={"external_id": settings.DEMO_EXTERNAL_ID},
        headers=_clerk_headers(),
        timeout=10,
    )
    r.raise_for_status()
    users = r.json()
    if users:
        return users[0]["id"]
    r = httpx.post(
        f"{settings.CLERK_API_URL}/users",
        headers=_clerk_headers(),
        json={
            "external_id": settings.DEMO_EXTERNAL_ID,
            "email_address": [settings.DEMO_EMAIL],
            "first_name": "Demo",
            "last_name": "Visitor",
            "skip_password_requirement": True,
            "skip_password_checks": True,
        },
        timeout=10,
    )
    r.raise_for_status()
    return r.json()["id"]


def create_demo_sign_in_ticket() -> str:
    """One-time Clerk sign-in ticket for the shared read-only demo account (no password exists)."""
    user_id = _find_or_create_demo_user()
    r = httpx.post(
        f"{settings.CLERK_API_URL}/sign_in_tokens",
        headers=_clerk_headers(),
        json={"user_id": user_id, "expires_in_seconds": 300},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()["token"]
