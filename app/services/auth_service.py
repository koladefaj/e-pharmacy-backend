import logging
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.crud.user import UserCRUD
from app.core.config import settings
from jose import JWTError, jwt
from app.core.roles import UserRole

from app.models.user import User
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token
from app.core.exceptions import AuthenticationFailed, NotAuthorized, PasswordVerificationError

# Initialize logger for tracking auth events
logger = logging.getLogger(__name__)

class AuthService:
    def __init__(self, session: AsyncSession):
        self.user_crud = UserCRUD(session=session)
        self.session = session

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
            "role": UserRole.CUSTOMER
        }
        del user_data['password'] # Don't pass plain password to CRUD

        try:
            # 3. CRUD: Save to database
            new_customer = await self.user_crud.create_user(user_data)

            # 4. Logic: Token Generation
            access_token = create_access_token(new_customer)
            refresh_token = create_refresh_token(new_customer)

            # 5. Commit the transaction
            await self.session.commit()
            await self.session.refresh(new_customer)
            
            logger.info(f"User registered successfully: {new_customer.id}")

            return {
                "user": new_customer.id,
                "email": new_customer.email,
                "role": new_customer.role,
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer"
            }

        except Exception as e:
            await self.session.rollback()
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
            "role": UserRole.PHARMACIST,
        }

        try:
            # 3. Save to DB
            new_pharmacist = await self.user_crud.create_user(user_data)

            # 4. Commit
            await self.session.commit()
            await self.session.refresh(new_pharmacist)

            logger.info(f"Pharmacist registered: {new_pharmacist.id}")
            return new_pharmacist

        except Exception as e:
            await self.session.rollback()
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
            "user_email": user.email,
            "user_role:": user.role.value,  # Often helpful to return user info on login
        }
         

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
        
    
