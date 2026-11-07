from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: str
    org_id: str
    email: str
    full_name: str
    role: str
    is_active: bool
    is_demo: bool = False
    org_name: str | None = None

    model_config = {"from_attributes": True}
