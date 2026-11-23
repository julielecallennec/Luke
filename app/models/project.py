from typing import List, Optional, Literal
from pydantic import BaseModel, Field
from app.models.user import UserResponse


ProjectStatusType = Literal["ACTIVE", "ARCHIVED"]


class ProjectBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=150, examples=["Refonte Site E-commerce"])
    description: str = Field(default="", examples=["Développement de la nouvelle boutique en ligne mobile-first"])
    status: ProjectStatusType = Field(default="ACTIVE", examples=["ACTIVE"])
    member_ids: List[str] = Field(default_factory=list, examples=[[]])


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=150)
    description: Optional[str] = None
    status: Optional[ProjectStatusType] = None
    member_ids: Optional[List[str]] = None


class ProjectResponse(BaseModel):
    id: str
    company_id: str
    name: str
    description: str
    status: str
    member_ids: List[str]
    created_at: str
    updated_at: str
    
    # Données enrichies pour l'interface
    members: Optional[List[UserResponse]] = []
    total_tasks: Optional[int] = 0
    done_tasks: Optional[int] = 0
    progress_percentage: Optional[int] = 0
