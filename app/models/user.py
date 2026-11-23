from typing import Optional, Literal
from pydantic import BaseModel, EmailStr, Field


RoleType = Literal["ADMIN", "MEMBER"]


class UserBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, examples=["Alice Martin"])
    email: EmailStr = Field(..., examples=["alice@agence-creative.fr"])
    role: RoleType = Field(default="MEMBER", examples=["ADMIN"])
    avatar_color: str = Field(default="#4F46E5", pattern=r"^#[0-9a-fA-F]{6}$", examples=["#4F46E5"])


class UserCreate(UserBase):
    password: Optional[str] = Field("secret123", min_length=6, examples=["secret123"])


class UserUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    email: Optional[EmailStr] = None
    role: Optional[RoleType] = None
    avatar_color: Optional[str] = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")
    password: Optional[str] = Field(None, min_length=6)


class UserResponse(BaseModel):
    id: str
    company_id: str
    name: str
    email: str
    role: str
    avatar_color: str
    created_at: str
