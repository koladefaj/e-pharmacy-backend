import asyncio
import os
from datetime import date

from sqlalchemy import select

from app.core.roles import UserRole
from app.core.security import hash_password
from app.db.sessions import get_async_session
from app.models.user import User


async def create_super_admin():
    # Use the session generator
    password = os.environ.get("ADMIN_PASSWORD")
    if not password:
        raise RuntimeError("ADMIN_PASSWORD env var not set")

    async for session in get_async_session():
        # Check if admin already exists
        email = "akoladefvr@gmail.com"
        result = await session.execute(select(User).where(User.email == email))

        if result.scalar_one_or_none():
            print("Admin already exists!")
            return

        admin = User(
            full_name="System Admin",
            email=email,
            hashed_password=hash_password(password),
            role=UserRole.ADMIN.value, 
            is_active=True,
            phone_number="+2340000000000",
            date_of_birth=date(2004, 1, 1),
            address="Store Head Office"
        )
        
        session.add(admin)
        await session.commit()
        print(f"Successfully created admin: {email}")

if __name__ == "__main__":
    asyncio.run(create_super_admin())