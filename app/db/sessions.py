import logging
from app.core.config import settings
from sqlalchemy.ext.asyncio import (AsyncSession, async_sessionmaker, create_async_engine)

# Initialize the logger for async database events
logger = logging.getLogger(__name__)

# DATABASE URL CONFIGURATION

# Get the base DATABASE_URL (sync version: postgresql://)
db_url = settings.database_url

if not db_url:
    raise RuntimeError("DATABASE_URL is not set")

if db_url.startswith("postgresql+asyncpg://"):
    async_db = db_url
else:
    #create async version for the application
    async_db = db_url.replace('postgresql://', 'postgresql+asyncpg://')


# ASYNC ENGINE CONFIG (FastAPI)

async_engine = create_async_engine(
    async_db,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_= AsyncSession,
    expire_on_commit= False,
)


# FASTAPI DEPENDENCY
async def get_async_session() -> AsyncSession:
    """
    FastAPI Dependency that provides an asynchronous database session.
    """
    async with AsyncSessionLocal() as session:
        try:
            logger.debug("Database: New async session yielded for API request.")
            yield session
        except Exception as e:
            await session.rollback()
            logger.exception(f"Database: Async session error: {e}")
            raise
        finally:
            await session.close()

