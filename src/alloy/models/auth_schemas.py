from enum import Enum
from pydantic import BaseModel, EmailStr, Field, model_validator

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class RoleEnum(str, Enum):
    volunteer = "Volunteer"
    organizer = "Organizer"
    admin = "Admin"

class StatusEnum(str, Enum):
    active = "Active"
    blocked = "Blocked"

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=72)
    password_confirm: str = Field(..., min_length=8, max_length=72)
    role: RoleEnum
    agreed_to_rules: bool

    @model_validator(mode='after')
    def validate_registration_rules(self) -> 'UserCreate':
        if self.password != self.password_confirm:
            raise ValueError("Passwords do not match")

        if not self.agreed_to_rules:
            raise ValueError("You must agree to the platform rules")

        if self.role == RoleEnum.admin:
            raise ValueError("Cannot register an administrator through this path")

        return self

class UserResponse(BaseModel):
    id: str
    email: EmailStr
    role: RoleEnum
    status: StatusEnum
