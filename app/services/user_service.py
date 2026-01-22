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

class UserService:
    def __init__(self, session: AsyncSession = Depends(get_async_session)):
        self.user_crud = UserCRUD(session=session)
    
    async def delete_user_account(self, user_id: UUID) -> None:
        """
        Handles soft-deletion and anonymization of a user account.
        """
        # 1. Fetch user
        user = await self.user_crud.get_by_id(user_id)

        if not user:
            raise AuthenticationFailed("User not found.")
        
        if user.role != UserRole.CUSTOMER.value:
            raise NotAuthorized("You cannot perform this action")
        
        # 2. Soft delete / Anonymize
        user.is_active = False
        user.email = f"deleted_{user.id}@deleted.local"  # Using .local to avoid real domains
        user.hashed_password = "DEACTIVATED_ACCOUNT" # Faster than re-hashing
        
        try:
            # 3. Commit
            await self.user_crud.session.commit()
            logger.info(f"User account {user_id} deactivated and anonymized.")
        except Exception as e:
            await self.user_crud.session.rollback()
            logger.error(f"Failed to delete user {user_id}: {str(e)}")
            raise

    
    async def change_password(self, user_id: UUID, old_password: str, new_password: str) -> None:
        """
        Verifies old password and updates to a new hashed password.
        """
        # 1. Fetch user
        user = await self.user_crud.get_by_id(user_id)
        if not user:
            logger.warning(f"Password change failed: User {user_id} not found.")
            raise AuthenticationFailed("User not found.")

        # 2. Verify Old Password
        if not verify_password(old_password, user.hashed_password):
            logger.warning(f"Password change failed: Incorrect old password for user {user_id}")
            raise PasswordVerificationError("Old password is incorrect.")
            
        # 3. Security Logic: Prevent setting the same password
        # (Optional but recommended for production)
        if verify_password(new_password, user.hashed_password):
            raise PasswordVerificationError("New password cannot be the same as the old password.")

        # 4. Hash and Update
        user.hashed_password = hash_password(new_password)

        try:
            # 5. Commit
            await self.user_crud.session.commit()
            logger.info(f"Password updated successfully for user {user_id}")
        except Exception as e:
            await self.user_crud.session.rollback()
            logger.error(f"Error updating password for {user_id}: {str(e)}")
            raise


