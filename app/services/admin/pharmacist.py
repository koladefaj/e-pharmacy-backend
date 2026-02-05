import logging
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.crud.user import UserCRUD
from fastapi import HTTPException
from starlette import status
from app.schemas.pharmacist import PharmacistApproveSchema
from app.core.roles import UserRole
from app.core.exceptions import AuthenticationFailed

from app.models.user import User
from app.core.security import hash_password
from app.services.notification.notification_service import NotificationService
from fastapi import BackgroundTasks

# Initialize logger for tracking auth events
logger = logging.getLogger(__name__)

class AdminPharmacistService:
    def __init__(self, session: AsyncSession, notification_service: NotificationService):
        self.user_crud = UserCRUD(session=session)
        self.session = session
        self.notification_service = notification_service


    async def register_pharmacist(self, user_in: dict, background_tasks: BackgroundTasks) -> User:
        """Handles logic for pharmacist registration."""
        email = user_in['email'].lower()
        
        # Check existence
        if await self.user_crud.get_by_email(email):
            logger.warning(f"Registration failed: Pharmacist {email} already exists.")
            raise AuthenticationFailed("A user with this email is already registered.")

        # Prepare Data
        # We extract password to hash it and set the specific role
        password = user_in.pop('password')
        user_data = {
            **user_in,
            "email": email,
            "hashed_password": hash_password(password),
            "role": UserRole.PHARMACIST,
        }

        try:
        
            new_pharmacist = await self.user_crud.create_user(user_data)

            # Commit
            await self.session.commit()
            await self.session.refresh(new_pharmacist)

            # Unified Notification Logic
            if not new_pharmacist.license_verified:
                msg = f"Hi {new_pharmacist.full_name}, your account is created. Please submit your license for activation."
            else:
                msg = f"Hi {new_pharmacist.full_name}, your pharmacist account is ready!"

            background_tasks.add_task(
                self.notification_service.notify,
                email=new_pharmacist.email,
                phone=None,
                channels=["email"],
                message=msg
            )

            
            logger.info(f"Pharmacist registered: {new_pharmacist.id}")

            
            return new_pharmacist

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Pharmacist registration Failed: {str(e)}")
            raise
    
    async def deactivate_pharmacist_by_email(self, email: str) -> None:
        """
        Soft-deletes and anonymizes a pharmacist account.
        """
        # Fetch user by email
        user = await self.user_crud.get_by_email(email.lower())
        
        if not user:
            logger.warning(f"Deactivation failed: Pharmacist {email} not found.")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pharmacist not found"
            )
        
        
        # Anonymize and Deactivate
        user.is_active = False
        user.email = f"deleted_pharma_{user.id}@deleted.local"
        user.hashed_password = "DEACTIVATED_PHARMACIST" 
        
        # clear license info for GDPR/Privacy
        if hasattr(user, 'license_number'):
            user.license_number = f"DEL_{user.id}"

        try:
            # Commit
            await self.session.commit()


        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error deactivating pharmacist {email}: {str(e)}")
            raise
        
    async def get_pharmacist_list(self, skip: int, limit: int):
        return await self.user_crud.get_all_pharmacists(skip=skip, limit=limit)

    async def approve_pharmacist_account(self, pharmacist_id: UUID, approve_data: PharmacistApproveSchema, admin_email: str):
        # Fetch
        pharmacist = await self.user_crud.get_by_id(pharmacist_id)
        
        # Validation
        if not pharmacist or pharmacist.role != UserRole.PHARMACIST:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="Pharmacist not found"
            )
        
        if pharmacist.license_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Pharmacist already approved"
            )

        # Action
        updated_pharmacist = await self.user_crud.verify_pharmacist( 
            db_obj=pharmacist, 
            obj_in=approve_data
        )

        # Audit Log
        logger.info(f"AUDIT: Pharmacist {pharmacist.email} approved by Admin {admin_email}")

        
        return updated_pharmacist


