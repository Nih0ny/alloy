from typing import Self, Optional
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
    def validate_registration_rules(self) -> Self:
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

class OAuthProviderEnum(str, Enum):
    google = "google"
    facebook = "facebook"

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordConfirmRequest(BaseModel):
    reset_token: str = Field(..., description="Reset token received via email")
    new_password: str = Field(..., min_length=8, max_length=72, description="New password (minimum 8 characters)")
    new_password_confirm: str = Field(..., min_length=8, max_length=72, description="Confirmation of the new password")

    @model_validator(mode="after")
    def check_passwords_match(self) -> Self:
        if self.new_password != self.new_password_confirm:
            raise ValueError("New password and confirmation do not match")
        return self

class OAuthLoginRequest(BaseModel):
    token: str = Field(
        ...,
        description="OAuth Access Token or ID Token received by the client from Google or Facebook SDK"
    )
    role: Optional[RoleEnum] = Field(
        RoleEnum.volunteer,
        description="Role for a new user upon first registration via OAuth ('Volunteer' or 'Organizer')"
    )
    agreed_to_rules: bool = Field(
        True,
        description="Agreement with the platform rules"
    )

    @model_validator(mode="after")
    def validate_oauth_role(self) -> Self:
        if self.role == RoleEnum.admin:
            raise ValueError("Cannot select Administrator role")
        if not self.agreed_to_rules:
            raise ValueError("You must agree to the platform rules")
        return self

class AuthUserResponse(BaseModel):
    id: str
    email: EmailStr
    role: RoleEnum
    status: StatusEnum
    is_email_verified: bool = False
    access_token: str
    token_type: str = "bearer"

class VerifyEmailRequest(BaseModel):
    verification_token: str = Field(..., description="Email verification token received via email")

class ResendVerificationRequest(BaseModel):
    email: EmailStr

UserCreate.model_rebuild()
ResetPasswordConfirmRequest.model_rebuild()
OAuthLoginRequest.model_rebuild()
