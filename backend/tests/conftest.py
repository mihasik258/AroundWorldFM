import os
from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.api.deps import get_db
from app.core.security import hash_password
from app.db.base import Base
from app.main import app
from app.models.identity import UserIdentity
from app.models.user import User, UserRole

# Isolated test database URL
TEST_DB_URL = os.getenv("TEST_DATABASE_URL", "postgresql+asyncpg://postgres:postgrespassword@localhost:5432/aroundfm_test")

test_engine = create_async_engine(
    TEST_DB_URL,
    poolclass=NullPool,
    echo=False,
)

TestingSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_schema():
    """Initializes schema once per test session."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provides a fresh database session per test and truncates tables afterwards."""
    async with TestingSessionLocal() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE users, user_identities, user_sessions, stations, station_streams, stream_health, favorites RESTART IDENTITY CASCADE;"
            )
        )


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Provides an async HTTP test client using the test database session."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def create_users(db_session: AsyncSession):
    """Creates a regular user and an admin user with UserIdentity in the test database."""
    user = User(
        email="testuser@example.com",
        username="testuser",
        role=UserRole.USER,
        is_active=True,
    )
    admin = User(
        email="adminuser@example.com",
        username="adminuser",
        role=UserRole.ADMIN,
        is_active=True,
    )
    db_session.add_all([user, admin])
    await db_session.flush()

    user_id = UserIdentity(
        user_id=user.id,
        provider="password",
        provider_uid="testuser",
        secret_hash=hash_password("Password123!"),
    )
    admin_id = UserIdentity(
        user_id=admin.id,
        provider="password",
        provider_uid="adminuser",
        secret_hash=hash_password("AdminPassword123!"),
    )
    db_session.add_all([user_id, admin_id])
    await db_session.commit()
    await db_session.refresh(user)
    await db_session.refresh(admin)
    return {"user": user, "admin": admin}

