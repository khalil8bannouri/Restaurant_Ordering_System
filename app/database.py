"""
Database Connection Module
Handles PostgreSQL connection using SQLAlchemy async engine.
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
import os

# Database URL - Using psycopg async with port 5433
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://restaurant_admin:secretpassword123@localhost:5433/restaurant_orders"
)

# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=True,  # Set to False in production (logs all SQL queries)
    pool_size=5,  # Connection pool size
    max_overflow=10  # Extra connections when pool is full
)

# Session factory - creates new database sessions
async_session_maker = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False  # Objects remain accessible after commit
)


# Base class for all our models
class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    """
    Dependency injection for FastAPI routes.
    Yields a database session and ensures cleanup.
    """
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """
    Create all tables in database.
    Called once at application startup.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Database tables created successfully!")