from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

# ROle read
class RoleRead(BaseModel):
    id: int
    name: str
    #role_number: int

    model_config = {"from_attributes": True}

# For reading user data
class UserRead(BaseModel):
    id: int
    username: str
    email: EmailStr
    role: RoleRead
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


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
    role_number_fk: Optional[int] = None

    class Config:
        extra = "ignore"


# For login in
class UserLogin(BaseModel):
    username: str
    password: str


#class RoleRead(BaseModel):
#    id: int
#    name: str
#    #role_id: int
#
#    class Config:
#        orm_mode = True


class RoleCreate(BaseModel):
    name: str
    role_id: int