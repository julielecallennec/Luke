"""Pydantic request and response schemas for Luke."""
from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, EmailStr, field_validator

TaskStatus = Literal["TODO", "IN_PROGRESS", "IN_REVIEW", "DONE"]
Priority = Literal["LOW", "MEDIUM", "HIGH"]
Role = Literal["ADMIN", "MEMBER"]
ProjectStatus = Literal["ACTIVE", "ARCHIVED"]


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class CompanyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    slug: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    plan: str = "PRO"


class CompanyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    slug: str | None = Field(default=None, min_length=2, max_length=80, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    plan: str | None = None


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    role: Role = "MEMBER"
    avatar_color: str = Field(default="#4F46E5", pattern=r"^#[0-9A-Fa-f]{6}$")


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    email: EmailStr | None = None
    role: Role | None = None
    avatar_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    member_ids: list[str] = Field(default_factory=list)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    status: ProjectStatus | None = None
    member_ids: list[str] | None = None


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=5000)
    status: TaskStatus = "TODO"
    priority: Priority = "MEDIUM"
    assignee_id: str | None = None
    tags: list[str] = Field(default_factory=list, max_length=10)
    due_date: datetime | None = None


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=5000)
    status: TaskStatus | None = None
    priority: Priority | None = None
    assignee_id: str | None = None
    tags: list[str] | None = Field(default=None, max_length=10)
    due_date: datetime | None = None


class TaskMove(BaseModel):
    status: TaskStatus
    position: int = Field(ge=0)


class DocumentModel(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    id: str = Field(alias="_id")
