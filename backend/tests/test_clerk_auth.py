"""Clerk session verification, user provisioning, read-only viewers and demo access."""
import time
import uuid

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwk, jwt

from app.core import clerk
from app.core.config import settings
from app.models.user import User

ISSUER = "https://test-instance.clerk.accounts.dev"


@pytest.fixture
def rsa_key(monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    from cryptography.hazmat.primitives import serialization

    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    pub = jwk.construct(
        key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo),
        "RS256",
    ).to_dict()
    pub.update(kid="test-kid", use="sig")
    monkeypatch.setattr(settings, "CLERK_ISSUER", ISSUER)
    monkeypatch.setattr(settings, "CLERK_AUTHORIZED_PARTIES", "http://localhost:3001")
    monkeypatch.setattr(clerk, "_get_jwks", lambda force=False: [pub])
    return pem


def _token(pem, sub="user_abc", azp="http://localhost:3001", exp_in=60, iss=ISSUER):
    now = int(time.time())
    return jwt.encode(
        {"sub": sub, "iss": iss, "azp": azp, "iat": now, "nbf": now, "exp": now + exp_in},
        pem,
        algorithm="RS256",
        headers={"kid": "test-kid"},
    )


def _fake_clerk_user(email, external_id=None):
    return lambda cid: {
        "id": cid,
        "first_name": "Asha",
        "last_name": "Rao",
        "external_id": external_id,
        "primary_email_address_id": "e1",
        "email_addresses": [{"id": "e1", "email_address": email}],
    }


def test_valid_clerk_token_provisions_viewer(client, db, test_org, rsa_key, monkeypatch):
    monkeypatch.setattr(clerk, "_fetch_clerk_user", _fake_clerk_user("asha@example.com"))
    tok = _token(rsa_key, sub="user_new1")
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["role"] == "viewer" and body["full_name"] == "Asha Rao"
    assert db.query(User).filter(User.clerk_user_id == "user_new1").count() == 1


def test_admin_email_is_provisioned_as_admin(client, db, test_org, rsa_key, monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_EMAILS", "owner@example.com")
    monkeypatch.setattr(clerk, "_fetch_clerk_user", _fake_clerk_user("owner@example.com"))
    tok = _token(rsa_key, sub="user_owner")
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tok}"}).json()["role"] == "admin"


@pytest.mark.parametrize(
    "kwargs",
    [{"exp_in": -120}, {"iss": "https://evil.example"}, {"azp": "https://evil.example"}],
)
def test_bad_clerk_tokens_rejected(client, test_org, rsa_key, monkeypatch, kwargs):
    monkeypatch.setattr(clerk, "_fetch_clerk_user", _fake_clerk_user("x@example.com"))
    tok = _token(rsa_key, **kwargs)
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tok}"}).status_code == 401


def test_viewer_is_read_only_but_can_read(client, db, test_org, rsa_key, monkeypatch):
    monkeypatch.setattr(clerk, "_fetch_clerk_user", _fake_clerk_user("viewer@example.com"))
    h = {"Authorization": f"Bearer {_token(rsa_key, sub='user_v')}"}
    assert client.get("/api/v1/collections/today", headers=h).status_code == 200
    r = client.post(f"/api/v1/collections/invoices/{uuid.uuid4()}/dispute", json={"disputed": True}, headers=h)
    assert r.status_code == 403 and "Read-only" in r.json()["detail"]


def test_local_jwt_rejected_when_disabled(client, auth_headers, monkeypatch):
    monkeypatch.setattr(settings, "ALLOW_LOCAL_JWT", False)
    assert client.get("/api/v1/auth/me", headers=auth_headers).status_code == 401
    assert client.post("/api/v1/auth/login", json={"email": "a", "password": "b"}).status_code == 404


def test_demo_endpoint(client, monkeypatch):
    assert client.post("/api/v1/auth/demo").status_code == 404  # disabled by default in tests
    monkeypatch.setattr(settings, "DEMO_ENABLED", True)
    monkeypatch.setattr(settings, "CLERK_SECRET_KEY", "sk_test_dummy")
    import app.api.v1.auth as auth_api

    monkeypatch.setattr(auth_api, "create_demo_sign_in_ticket", lambda: "ticket_123")
    r = client.post("/api/v1/auth/demo")
    assert r.status_code == 200 and r.json() == {"ticket": "ticket_123"}
    assert client.get("/api/v1/auth/config").json()["demo_enabled"] is True


def test_demo_user_is_never_admin(client, db, test_org, rsa_key, monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_EMAILS", settings.DEMO_EMAIL)
    monkeypatch.setattr(clerk, "_fetch_clerk_user", _fake_clerk_user(settings.DEMO_EMAIL, settings.DEMO_EXTERNAL_ID))
    body = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {_token(rsa_key, sub='user_demo')}"}).json()
    assert body["role"] == "viewer" and body["is_demo"] is True
