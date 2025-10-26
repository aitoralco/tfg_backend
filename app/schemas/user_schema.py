from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

# For reading user data
class UserRead(BaseModel):
    id: int
    username: str
    email: EmailStr
    role: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


# For creating a new user
class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str


#For updating user data
class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    role: Optional[int] = None


# For login in
class UserLogin(BaseModel):
    username: str
    password: str