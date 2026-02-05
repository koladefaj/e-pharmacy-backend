from pydantic import BaseModel, ConfigDict, EmailStr
from datetime import datetime
from uuid import UUID



class PharmacistInDB(BaseModel):
    id: UUID
    full_name: str
    email: EmailStr
    phone_number: str
    license_number: str
    license_verified: bool
    is_active: bool
    hired_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)



class PharmacistRead(PharmacistInDB):
    """
    Read all pharmacists

    """
    model_config = ConfigDict(from_attributes=True)

class PharmacistInDB(BaseModel):
    id: UUID
    full_name: str
    email: EmailStr
    phone_number: str
    license_number: str
    license_verified: bool
    is_active: bool
    hired_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class PharmacistApproveSchema(BaseModel):
    license_verified: bool
