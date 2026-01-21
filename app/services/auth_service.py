import logging
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.crud.user import UserCRUD
from fastapi import Depends
from app.db.sessions import get_async_session
from app.core.config import settings
from jose import JWTError, jwt
from app.core.roles import UserRole

from app.models.user import User
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token
from app.core.exceptions import AuthenticationFailed, NotAuthorized, PasswordVerificationError

# Initialize logger for tracking auth events
logger = logging.getLogger(__name__)

class AuthService:
    def __init__(self, session: AsyncSession = Depends(get_async_session)):
        self.user_crud = UserCRUD(session=session)

    async def register_customer(self, user_in: dict):
        email = user_in['email'].lower()
        
        # 1. Logic: Check existence
        existing_user = await self.user_crud.get_by_email(email)
        if existing_user:
            logger.warning(f"Registration failed: User {email} already exists.")
            raise AuthenticationFailed("A user with this email is already registered.")

        # 2. Logic: Prepare data (hashing & roles)
        user_data = {
            **user_in,
            "email": email,
            "hashed_password": hash_password(user_in['password']),
            "role": UserRole.CUSTOMER.value
        }
        del user_data['password'] # Don't pass plain password to CRUD

        try:
            # 3. CRUD: Save to database
            new_customer = await self.user_crud.create_user(user_data)

            # 4. Logic: Token Generation
            access_token = create_access_token(new_customer)
            refresh_token = create_refresh_token(new_customer)

            # 5. Commit the transaction
            await self.user_crud.session.commit()
            await self.user_crud.session.refresh(new_customer)
            
            logger.info(f"User registered successfully: {new_customer.id}")

            return {
                "user": new_customer,
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer"
            }

        except Exception as e:
            await self.user_crud.session.rollback()
            logger.error(f"Database error during registration: {str(e)}")
            raise


    async def register_pharmacist(self, user_in: dict) -> User:
        """Handles logic for pharmacist registration."""
        email = user_in['email'].lower()
        
        # 1. Check existence
        if await self.user_crud.get_by_email(email):
            logger.warning(f"Registration failed: Pharmacist {email} already exists.")
            raise AuthenticationFailed("A user with this email is already registered.")

        # 2. Prepare Data
        # We extract password to hash it and set the specific role
        password = user_in.pop('password')
        user_data = {
            **user_in,
            "email": email,
            "hashed_password": hash_password(password),
            "role": UserRole.PHARMACIST.value,
        }

        try:
            # 3. Save to DB
            new_pharmacist = await self.user_crud.create_user(user_data)

            # 4. Commit
            await self.user_crud.session.commit()
            await self.user_crud.session.refresh(new_pharmacist)

            logger.info(f"Pharmacist registered (pending verification): {new_pharmacist.id}")
            return new_pharmacist

        except Exception as e:
            await self.user_crud.session.rollback()
            logger.error(f"Database error during pharmacist registration: {str(e)}")
            raise

    async def login(self, email: str, password: str) -> dict:
        """
        Validates user credentials and issues tokens.
        """
        email = email.lower()

        # 1. Fetch user via CRUD
        user = await self.user_crud.get_by_email(email)

        # 2. Verify identity and status
        # Security Tip: We check both user existence and password in one block 
        # to prevent timing attacks that could reveal if an email exists.
        if not user or not verify_password(password, user.hashed_password):
            logger.warning(f"Login failed: Invalid credentials for {email}")
            raise PasswordVerificationError("Invalid email or password.")
        
        if not user.is_active:
            logger.warning(f"Login blocked: Account disabled for {email}")
            raise AuthenticationFailed("User account is inactive. Please contact support.")

        # 3. Generate tokens
        logger.info(f"Login successful: User {user.id}")
        
        return {
            "access_token": create_access_token(user),
            "refresh_token": create_refresh_token(user),
            "token_type": "bearer",
            "user": user  # Often helpful to return user info on login
        }
    
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
            logger.info(f"Pharmacist account {user.id} deactivated successfully.")


        except Exception as e:
            await self.user_crud.session.rollback()
            logger.error(f"Error deactivating pharmacist {email}: {str(e)}")
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

    async def refresh_access_token(self, refresh_token: str) -> dict:
        """
        Validates a refresh token and issues a new access token.
        """
        try:
            # 1. Decode and Validate JWT
            payload = jwt.decode(
                refresh_token,
                settings.secret_key,
                algorithms=[settings.jwt_algorithm]
            )

            # 2. Check Token Type
            if payload.get("type") != "refresh":
                raise AuthenticationFailed("Invalid token type")

            user_id = payload.get("sub")
            if not user_id:
                raise AuthenticationFailed("Token payload missing subject")

            # 3. Fetch User via CRUD
            user = await self.user_crud.get_by_id(UUID(user_id))

            # 4. Identity & Status Check
            if not user or not user.is_active:
                logger.warning(f"Refresh failed: User {user_id} not found or inactive")
                raise AuthenticationFailed("User not found or inactive")

            # 5. Generate New Access Token
            logger.info(f"Access token refreshed for user: {user.id}")
            new_access_token = create_access_token(user)

            return {
                "access_token": new_access_token,
                "token_type": "bearer",
            }

        except (JWTError, ValueError) as e:
            logger.error(f"Refresh token validation failed: {str(e)}")
            raise AuthenticationFailed("Token expired or invalid")


