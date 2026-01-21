from datetime import date
import uuid
from typing import Optional
import re

from pydantic import BaseModel, Field, EmailStr, ConfigDict, field_validator

# Regex for international phone numbers: +[CountryCode][Number]
PHONE_REGEX = r"^\+?[1-9]\d{1,14}$"


class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# Login Request
class LoginRequest(BaseModel):
    """Schema for user login credentials."""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, max_length=100)

# CUSTOMER REGISTRATION
class RegisterCustomerRequest(BaseSchema):
    full_name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8)
    address: str
    date_of_birth: date
    phone_number: str = Field(
        ...,
        description="International format, e.g., +2348012345678"
    )

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        if not re.match(PHONE_REGEX, value):
            raise ValueError("Invalid phone number format")
        return value



# PHARMACIST CREATION 
class CreatePharmacistRequest(BaseSchema):
    full_name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    phone_number: str
    address: str
    license_number: str = Field(..., min_length=3)
    date_of_birth: date
    hired_at: Optional[date]
    license_verified: Optional [bool]
    password: str = Field(..., min_length=8)

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        if not re.match(PHONE_REGEX, value):
            raise ValueError("Invalid phone number format")
        return value
    
class DeletePharmacistRequest(BaseSchema):
    email: EmailStr
    

# Change Password Request
class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., min_length=8)
    new_password: str = Field(..., min_length=8)


# USER RESPONSE (API OUTPUT)
class UserRead(BaseSchema):
    id: uuid.UUID
    full_name: str
    email: EmailStr
    phone_number: str
    role: str
    is_active: bool


class RefreshTokenRequest(BaseModel):
    refresh_token: str

