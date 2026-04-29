# app/schemas/auth_request.py
"""Authentication request schemas."""
from typing import Optional
import re

from pydantic import BaseModel, EmailStr, Field, field_validator


class UserLogin(BaseModel):
    """User login request."""
    email: Optional[EmailStr] = None
    username: Optional[str] = Field(None, min_length=2, max_length=50)
    password: str


class UserRegister(BaseModel):
    """Normal user registration request."""
    email: EmailStr
    username: str = Field(..., min_length=2, max_length=50, description="Username")
    phone: Optional[str] = Field(None, description="Optional phone number")
    password: str = Field(..., min_length=6, description="Password, at least 6 characters")
    full_name: Optional[str] = Field(None, min_length=2, max_length=100, description="Full name")
    nickname: Optional[str] = Field(None, max_length=50, description="Nickname")
    invite_code: Optional[str] = Field(None, min_length=8, max_length=32, description="Enterprise invite code")

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v and not re.match(r"^1[3-9]\d{9}$", v):
            raise ValueError("Invalid phone number format")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
        return v


class AdminRegister(BaseModel):
    """Enterprise admin registration request."""
    email: EmailStr
    username: str = Field(..., min_length=2, max_length=50, description="Username")
    phone: Optional[str] = Field(None, description="Optional phone number")
    password: str = Field(..., min_length=6, description="Password, at least 6 characters")
    full_name: str = Field(..., min_length=2, max_length=100, description="Full name")
    company_name: str = Field(..., min_length=2, max_length=200, description="Company name")
    company_position: Optional[str] = Field(None, max_length=100, description="Company position")
    nickname: Optional[str] = Field(None, max_length=50, description="Nickname")

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v and not re.match(r"^1[3-9]\d{9}$", v):
            raise ValueError("Invalid phone number format")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
        return v


class ChangePasswordRequest(BaseModel):
    """Change password request."""
    old_password: str = Field(..., description="Old password")
    new_password: str = Field(..., min_length=6, description="New password, at least 6 characters")

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("New password must be at least 6 characters")
        return v


class UpdatePhoneRequest(BaseModel):
    """Update phone number request."""
    phone: str = Field(..., description="New phone number")

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        if not re.match(r"^1[3-9]\d{9}$", v):
            raise ValueError("Invalid phone number format")
        return v


class ChangeInviteCodeRequest(BaseModel):
    """Change enterprise invite code request."""
    new_invite_code: str = Field(..., min_length=8, max_length=32, description="New enterprise invite code")
    confirm_leave: bool = Field(False, description="Confirm leaving the current enterprise")
