from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas import ORMModel, UserBrief, UserOut


class PermissionsMeta(BaseModel):
    modules: list[str]
    levels: list[str]


class CustomRoleIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    permissions: dict[str, str] = {}


class CustomRoleOut(ORMModel):
    id: int
    name: str
    permissions: dict[str, str]


class MeOut(UserOut):
    permissions: dict[str, str] = {}


class APITokenIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    user_id: int
    expires_days: int | None = Field(default=None, ge=1, le=3650)


class APITokenOut(ORMModel):
    id: int
    name: str
    user: UserBrief
    token_prefix: str
    created_at: datetime
    expires_at: datetime | None
    last_used_at: datetime | None


class APITokenCreated(BaseModel):
    token: str  # показується лише один раз
    item: APITokenOut
