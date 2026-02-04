import uuid
import re
from typing import Annotated
from datetime import date
from pydantic import BaseModel, Field, EmailStr, ConfigDict, field_validator, AfterValidator

# Regex for international phone numbers: +[CountryCode][Number]
PHONE_REGEX = r"^\+?[1-9]\d{1,14}$"

# Create a reusable, validated type
def validate_phone_number(v: str) -> str:
    if not re.match(PHONE_REGEX, v):
        raise ValueError("Invalid phone number format")
    return v

PhoneNumber = Annotated[str, AfterValidator(validate_phone_number)]

class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserBase(BaseSchema):
    full_name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    phone_number: PhoneNumber = Field(..., json_schema_extra={"example": "+234800000000"},)
    address: str
    date_of_birth: date

    @field_validator("date_of_birth")
    @classmethod
    def check_age(cls, v: date) -> date:
        if v >= date.today():
            raise ValueError("Date of birth must be in the past")
        return v


# Login Request
class LoginRequest(BaseModel):
    """Schema for user login credentials."""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, max_length=100)

# CUSTOMER REGISTRATION
class RegisterCustomerRequest(UserBase):
    password: str = Field(..., min_length=8, max_length=100)



# PHARMACIST CREATION 
class CreatePharmacistRequest(UserBase):
    license_number: str = Field(..., min_length=3)
    hired_at: date | None = None
    license_verified: bool | None = None
    password: str = Field(..., min_length=8)

    
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

