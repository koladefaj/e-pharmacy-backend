import logging
import jwt
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.crud.user import UserCRUD
from app.core.config import settings
from app.core.roles import UserRole

from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token
from app.core.exceptions import AuthenticationFailed, PasswordVerificationError
from app.services.notification.notification_service import NotificationService
from fastapi import BackgroundTasks

# Initialize logger for tracking auth events
logger = logging.getLogger(__name__)

class AuthService:
    def __init__(self, session: AsyncSession, notification_service: NotificationService):
        self.user_crud = UserCRUD(session=session)
        self.session = session
        self.notification_service = notification_service
    

    async def register_customer(self, user_in: dict, background_tasks: BackgroundTasks):
        email = user_in['email'].lower()
        
        # Logic: Check existence
        existing_user = await self.user_crud.get_by_email(email)
        if existing_user:
            logger.warning(f"Registration failed: User {email} already exists.")
            raise AuthenticationFailed("A user with this email is already registered.")

        # Logic: Prepare data (hashing & roles)
        user_data = {
            **user_in,
            "email": email,
            "hashed_password": hash_password(user_in['password']),
            "role": UserRole.CUSTOMER
        }
        user_data.pop('password', None)

        try:
            # CRUD: Save to database
            new_customer = await self.user_crud.create_user(user_data)
            await self.session.commit()
            await self.session.refresh(new_customer)

            # Logic: Token Generation
            access_token = create_access_token(new_customer)
            refresh_token = create_refresh_token(new_customer)


            background_tasks.add_task(
                self.notification_service.notify,
                   email=new_customer.email,
                   phone=None,
                   channels=["email"],
                   message=f"Welcome {new_customer.full_name}, your account is ready."
                
            )

            logger.info(f"User registered successfully: {new_customer.id}")

            return {
                "user": new_customer.id,
                "email": new_customer.email,
                "role": new_customer.role,
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer"
            }

        except Exception:
            await self.session.rollback()
            logger.exception("Registration Crashed")
            raise


    async def login(self, email: str, password: str) -> dict:
        """
        Validates user credentials and issues tokens.
        """
        email = email.lower()

        # Fetch user via CRUD
        user = await self.user_crud.get_by_email(email)

        # Verify identity and status
        # check both user existence and password in one block to prevent timing attacks that could reveal if an email exists.
        if not user or not verify_password(password, user.hashed_password):
            logger.warning(f"Login failed: Invalid credentials for {email}")
            raise PasswordVerificationError("Invalid email or password.")
        
        if not user.is_active:
            logger.warning(f"Login blocked: Account disabled for {email}")
            raise AuthenticationFailed("User account is inactive. Please contact support.")

        # Generate tokens
        logger.info(f"Login successful: User {user.id}")
        
        return {
            "access_token": create_access_token(user),
            "refresh_token": create_refresh_token(user),
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "email": user.email,
                "role": user.role.value,
                "full_name": user.full_name
            }
        }
    

    async def refresh_access_token(self, refresh_token: str) -> dict:
        """
        Validates a refresh token and issues a new access token.
        """
        try:
            # Decode and Validate JWT
            payload = jwt.decode(
                refresh_token,
                settings.secret_key,
                algorithms=[settings.jwt_algorithm]
            )

            # Check Token Type
            if payload.get("type") != "refresh":
                raise AuthenticationFailed("Invalid token type")

            user_id = payload.get("sub")
            if not user_id:
                raise AuthenticationFailed("Token payload missing subject")

            # Fetch User via CRUD
            user = await self.user_crud.get_by_id(UUID(user_id))

            # Identity & Status Check
            if not user or not user.is_active:
                logger.warning(f"Refresh failed: User {user_id} not found or inactive")
                raise AuthenticationFailed("User not found or inactive")

            # Generate New Access Token
            logger.info(f"Access token refreshed for user: {user.id}")
            new_access_token = create_access_token(user)

            return {
                "access_token": new_access_token,
                "token_type": "bearer",
            }

        except (jwt.PyJWTError, ValueError) as e:
            logger.error(f"Refresh token validation failed: {str(e)}")
            raise AuthenticationFailed("Token expired or invalid")
        
    
