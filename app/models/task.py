import uuid
from typing import List, Optional, Literal
from pydantic import BaseModel, Field
from app.models.user import UserResponse


TaskStatusType = Literal["TODO", "IN_PROGRESS", "IN_REVIEW", "DONE"]
TaskPriorityType = Literal["LOW", "MEDIUM", "HIGH"]


class SubTask(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    title: str = Field(..., min_length=1, max_length=200)
    done: bool = False


class SubTaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)


class SubTaskToggle(BaseModel):
    done: Optional[bool] = None


class TaskComment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    user_id: str
    user_name: str
    user_avatar_color: str = "#4F46E5"
    content: str = Field(..., min_length=1, max_length=2000)
    created_at: str


class TaskCommentCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)


class TaskBase(BaseModel):
    title: str = Field(..., min_length=2, max_length=200, examples=["Intégrer le paiement Stripe"])
    description: str = Field(default="", examples=["Mettre en place le formulaire de paiement"])
    status: TaskStatusType = Field(default="TODO", examples=["TODO"])
    priority: TaskPriorityType = Field(default="MEDIUM", examples=["HIGH"])
    position: Optional[int] = Field(default=0, examples=[0])
    tags: List[str] = Field(default_factory=list, examples=[["Backend", "Stripe"]])
    due_date: Optional[str] = Field(None, examples=["2026-11-15T18:00:00Z"])
    assignee_id: Optional[str] = Field(None, examples=["652a1b2c3d4e5f6a7b8c9d02"])
    subtasks: List[SubTask] = Field(default_factory=list)


class TaskCreate(TaskBase):
    project_id: str = Field(..., examples=["652a1b2c3d4e5f6a7b8c9d03"])


class TaskUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=2, max_length=200)
    description: Optional[str] = None
    status: Optional[TaskStatusType] = None
    priority: Optional[TaskPriorityType] = None
    position: Optional[int] = None
    tags: Optional[List[str]] = None
    due_date: Optional[str] = None
    assignee_id: Optional[str] = None
    subtasks: Optional[List[SubTask]] = None


class TaskMove(BaseModel):
    """
    Modèle pour le Drag & Drop Kanban :
    Permet de modifier le statut de la colonne et la position ordonnée au sein de la colonne.
    """
    status: TaskStatusType
    position: int = Field(..., ge=0)


class TaskResponse(BaseModel):
    id: str
    company_id: str
    project_id: str
    assignee_id: Optional[str] = None
    title: str
    description: str
    status: str
    priority: str
    position: int
    tags: List[str]
    due_date: Optional[str] = None
    subtasks: List[SubTask] = Field(default_factory=list)
    comments: List[TaskComment] = Field(default_factory=list)
    created_at: str
    updated_at: str
    
    # Données enrichies
    assignee: Optional[UserResponse] = None
