import logging
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.crud.user import UserCRUD
from fastapi import Depends, HTTPException
from app.db.sessions import get_async_session
from app.schemas.pharmacist import PharmacistApproveSchema
from app.core.config import settings
from jose import JWTError, jwt
from app.core.roles import UserRole

from app.models.user import User
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token
from app.core.exceptions import AuthenticationFailed, NotAuthorized, PasswordVerificationError

# Initialize logger for tracking auth events
logger = logging.getLogger(__name__)

class AdminPharmacistService:
    def __init__(self, session: AsyncSession = Depends(get_async_session)):
        self.user_crud = UserCRUD(session=session)
    
    async def deactivate_pharmacist_by_email(self, email: str) -> None:
        """
        Soft-deletes and anonymizes a pharmacist account.
        """
        # 1. Fetch user by email
        user = await self.user_crud.get_by_email(email.lower())
        
        if not user:
            logger.warning(f"Deactivation failed: Pharmacist {email} not found.")
            raise AuthenticationFailed("User not found.")
        
        # 2. Anonymize and Deactivate
        user.is_active = False
        user.email = f"deleted_pharma_{user.id}@deleted.local"
        user.hashed_password = "DEACTIVATED_PHARMACIST" # No need to hash if inactive
        
        # Optionally clear license info for GDPR/Privacy
        if hasattr(user, 'license_number'):
            user.license_number = f"DEL_{user.id}"

        try:
            # 3. Commit
            await self.user_crud.session.commit()


        except Exception as e:
            await self.user_crud.session.rollback()
            logger.error(f"Error deactivating pharmacist {email}: {str(e)}")
            raise
        
    async def get_pharmacist_list(self, skip: int, limit: int):
        return await self.user_crud.get_all_pharmacists(skip=skip, limit=limit)

    async def approve_pharmacist_account(self, pharmacist_id: UUID, approve_data: PharmacistApproveSchema, admin_email: str):
        # 1. Fetch
        pharmacist = await self.user_crud.get_by_id(pharmacist_id)
        
        # 2. Validation
        if not pharmacist or pharmacist.role != UserRole.PHARMACIST.value:
            raise HTTPException(status_code=404, detail="Pharmacist not found")
        
        if pharmacist.license_verified == True:
            return "Pharmacist already verified"

        # 3. Action
        updated_pharmacist = await self.user_crud.verify_pharmacist( 
            db_obj=pharmacist, 
            obj_in=approve_data
        )

        # 4. Audit Log
        logger.info(f"AUDIT: Pharmacist {pharmacist.email} approved by Admin {admin_email}")
        
        return updated_pharmacist


