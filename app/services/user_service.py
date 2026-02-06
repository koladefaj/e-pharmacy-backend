import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AuthenticationFailed,
    NotAuthorized,
    PasswordVerificationError,
)
from app.core.roles import UserRole
from app.core.security import hash_password, verify_password
from app.crud.user import UserCRUD

# Initialize logger for tracking auth events
logger = logging.getLogger(__name__)


class UserService:

    def __init__(self, session: AsyncSession):

        self.user_crud = UserCRUD(session)
        self.session = session

    async def delete_user_account(self, user_id: UUID) -> None:
        """
        Handles soft-deletion and anonymization of a user account.
        """
        # Fetch user
        user = await self.user_crud.get_by_id(user_id)

        if not user:
            raise AuthenticationFailed("User not found.")

        if user.role != UserRole.CUSTOMER:
            logger.warning(f"Security: Staff user {user_id} attempted self-deletion.")
            raise NotAuthorized("Staff accounts must be deactivated by an Admin.")

        # Soft delete + Anonymize PII
        user.is_active = False
        user.email = (
            f"deleted_{user.id}@deleted.local"  # Using .local to avoid real domains
        )
        user.hashed_password = "DEACTIVATED_ACCOUNT"  # Faster than re-hashing
        user.full_name = "Deleted User"
        user.phone_number = "N/A"
        user.address = "Anonymized"

        try:
            # Commit
            await self.session.commit()
            logger.info(f"User account {user_id} deactivated and anonymized.")
        except Exception:
            await self.session.rollback()
            logger.exception(f"Critical failure during user anonymization: {user_id}")
            raise

    async def change_password(
        self, user_id: UUID, old_password: str, new_password: str
    ) -> None:
        """
        Verifies old password and updates to a new hashed password.
        """
        # Fetch user
        user = await self.user_crud.get_by_id(user_id)
        if not user:
            raise AuthenticationFailed("User not found.")

        # Verify Old Password
        if not verify_password(old_password, user.hashed_password):
            logger.warning(
                f"Password change failed: Incorrect old password for user {user_id}"
            )
            raise PasswordVerificationError("Old password is incorrect.")

        # Security Logic: Prevent setting the same password
        if verify_password(new_password, user.hashed_password):
            raise PasswordVerificationError(
                "New password cannot be the same as the old password."
            )

        # Hash and Update
        user.hashed_password = hash_password(new_password)

        try:
            # Commit
            await self.session.commit()
            logger.info(f"Password updated successfully for user {user_id}")

        except Exception:
            await self.session.rollback()
            logger.exception(f"Error updating password for {user_id}")
            raise
