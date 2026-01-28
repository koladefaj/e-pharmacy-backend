import logging
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.pharmacist import PharmacistApproveSchema
from sqlalchemy import select
from app.core.roles import UserRole
from app.models.user import User

# Initialize logger for tracking auth events
logger = logging.getLogger(__name__)

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.user import User

class UserCRUD:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()
    
    async def get_by_id(self, user_id: UUID) -> User | None:
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def create_user(self, user_data: dict) -> User:
        new_user = User(**user_data)
        self.session.add(new_user)
        # We use flush here so the ID is populated, but commit happens in Service
        await self.session.flush() 
        return new_user
    
    async def get_all_pharmacists(self, skip: int = 0, limit: int = 10):
        stmt = (
            select(User)
            .where(User.role == UserRole.PHARMACIST.value, User.is_active == True)
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def verify_pharmacist(self, *, db_obj: User, obj_in: PharmacistApproveSchema):
        # This just updates the fields and saves
        db_obj.license_verified = True 
        db_obj.is_active = True
    
        await self.session.commit()
        await self.session.refresh(db_obj)
        return db_obj