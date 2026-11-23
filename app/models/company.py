from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field


PlanType = Literal["FREE", "PRO", "ENTERPRISE"]


class CompanyBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, examples=["Agence Web Créative"])
    slug: Optional[str] = Field(None, max_length=120, examples=["agence-web-creative"])
    plan: PlanType = Field(default="PRO", examples=["PRO"])


class CompanyCreate(CompanyBase):
    pass


class CompanyUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    slug: Optional[str] = Field(None, max_length=120)
    plan: Optional[PlanType] = None


class CompanyResponse(BaseModel):
    id: str
    name: str
    slug: str
    plan: str
    created_at: str
    updated_at: str
    
    # Données enrichies pour l'interface
    users_count: Optional[int] = 0
    projects_count: Optional[int] = 0
    tasks_count: Optional[int] = 0
