from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class RoleRead(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}


class UserRead(BaseModel):
    id: int
    username: str
    email: EmailStr
    role: RoleRead
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead


class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    username: str
    password: str


# Used by a regular user to update their own data — requires current password
class UserSelfUpdate(BaseModel):
    current_password: str
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    new_password: Optional[str] = None


# Used by an admin to update any user — no password verification required
class UserAdminUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    role_id: Optional[int] = None


class RoleCreate(BaseModel):
    name: str
    role_id: int
