import os

os.environ.setdefault("SECRET_KEY", "test-only-jwt-signing-key-0123456789abcdef")
os.environ.setdefault("SECRET_PEPPER", "test-only-password-pepper-0123456789abcdef")
TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgrespassword@localhost:5432/aroundfm_test",
)
os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["ENVIRONMENT"] = "test"
os.environ["STREAM_CHECK_ENABLED"] = "false"
os.environ["ALLOW_PRIVATE_STREAM_HOSTS"] = "true"
os.environ["COOKIE_SECURE"] = "true"

from collections.abc import AsyncGenerator
from pathlib import Path

import pytest_asyncio
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.api.deps import get_db
from app.core.cache import catalog_cache
from app.core.rate_limit import limiter
from app.core.security import hash_password
from app.main import app
from app.models.identity import UserIdentity
from app.models.user import User, UserRole

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


ALEMBIC_INI = Path(__file__).resolve().parent.parent / "alembic.ini"

TABLES = (
    "users, user_identities, auth_flows, user_sessions, stations, "
    "station_streams, stream_health, favorites, airports, flight_routes"
)


def _alembic(connection, revision: str, upgrade: bool) -> None:
    cfg = Config(str(ALEMBIC_INI))
    cfg.attributes["connection"] = connection
    if upgrade:
        command.upgrade(cfg, revision)
    else:
        command.downgrade(cfg, revision)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_schema():
    async with test_engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
    async with test_engine.begin() as conn:
        await conn.run_sync(_alembic, "head", True)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(_alembic, "base", False)


@pytest_asyncio.fixture(autouse=True)
async def reset_rate_limits():
    limiter.reset()
    yield


@pytest_asyncio.fixture(autouse=True)
async def reset_catalog_cache():
    catalog_cache.clear()
    yield


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with TestingSessionLocal() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def create_users(db_session: AsyncSession):
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


@pytest_asyncio.fixture
async def station(db_session: AsyncSession):
    from app.models.station import Station, StationStream, StreamHealth

    st = Station(
        name="Test FM",
        country="Testland",
        latitude=10.0,
        longitude=20.0,
        language="english",
        tags=["jazz", "chillout"],
        streams=[
            StationStream(
                stream_url="https://radio.example.com/live.mp3",
                is_primary=True,
                health=StreamHealth(is_active=True, check_fail_count=0),
            )
        ],
    )
    db_session.add(st)
    await db_session.commit()
    return st
