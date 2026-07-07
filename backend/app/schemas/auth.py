from typing import Literal

from pydantic import BaseModel, Field


AuthProviderType = Literal["household_select", "password", "oauth2"]


class AuthProvider(BaseModel):
    key: str
    type: AuthProviderType
    label: str
    enabled: bool
    configured: bool
    description: str


class AuthUserSummary(BaseModel):
    slug: str
    display_name: str
    username: str
    has_password: bool
    can_quick_select: bool


class AuthProvidersResponse(BaseModel):
    providers: list[AuthProvider]
    users: list[AuthUserSummary]


class UserSelectionRequest(BaseModel):
    user_slug: str = Field(min_length=1)


class PasswordLoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class SessionUser(BaseModel):
    slug: str
    display_name: str
    username: str
    auth_method: AuthProviderType


class SessionResponse(BaseModel):
    user: SessionUser
    session_mode: Literal["scaffold"]
    message: str

