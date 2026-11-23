from typing import Optional
from pydantic import BaseModel, Field

try:
    import email_validator  # noqa: F401
    from pydantic import EmailStr
except ImportError:
    EmailStr = str  # type: ignore

from app.models.user import UserResponse
from app.models.company import CompanyResponse


class LoginRequest(BaseModel):
    email: EmailStr = Field(..., examples=["alice@agence-creative.fr"])
    password: str = Field(..., min_length=1, examples=["alice123"])
    company_slug: Optional[str] = Field(None, examples=["agence-web-creative"])


class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, examples=["Lukas Toulelle"])
    email: EmailStr = Field(..., examples=["lukas@mon-saas.com"])
    password: str = Field(..., min_length=6, examples=["secret123"])
    company_name: Optional[str] = Field(None, min_length=2, max_length=100, examples=["Mon Entreprise SaaS"])
    company_slug: Optional[str] = Field(None, max_length=120, examples=["agence-web-creative"])


class ForgotPasswordRequest(BaseModel):
    email: EmailStr = Field(..., examples=["alice@agence-creative.fr"])


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=4, examples=["a1b2c3d4"])
    new_password: str = Field(..., min_length=6, examples=["nouveauSecret123"])


class AuthResponse(BaseModel):
    token: str
    user: UserResponse
    company: CompanyResponse
    message: Optional[str] = "Authentification réussie."
