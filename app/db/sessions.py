import logging
from contextlib import contextmanager
from app.core.config import settings
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.engine import create_engine
from sqlalchemy.ext.asyncio import (AsyncSession, async_sessionmaker, create_async_engine)

# Initialize the logger for async database events
logger = logging.getLogger(__name__)

# --- DATABASE URL CONFIGURATION ---

# Get the base DATABASE_URL (sync version: postgresql://)
db_url = settings.database_url

if not db_url:
    raise RuntimeError("DATABASE_URL is not set")

if db_url.startswith("postgresql+asyncpg://"):
    async_db = db_url
else:
    #create async version for the application
    async_db = db_url.replace('postgresql://', 'postgresql+asyncpg://')


# --- ASYNC ENGINE CONFIG (FastAPI)

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

# --- SYNC ENGINE CONFIG (Celery / Scripts)

sync_engine = create_engine(
    db_url,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    future=True,
)


SessionLocal = sessionmaker(
    bind=sync_engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False
)

# --- FASTAPI DEPENDENCY
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

# CELERY / WORKER USAGE

def get_sync_session() -> Session:
    """
    Standard synchronous DB session provider for Celery workers.
    
    """
    
    logger.debug("Database: Creating new synchronous session for worker.")
    return SessionLocal()

# --- CONTEXT MANAGER ---

@contextmanager
def sync_session_scope():
    """
    Provide a transactional scope around a series of operations.
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Database Scope Error: {e}")
        raise
    finally:
        session.close()