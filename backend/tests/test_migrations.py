import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

from app.db.base import Base
from tests.conftest import test_engine


def _diff(connection):
    context = MigrationContext.configure(
        connection, opts={"compare_type": True, "compare_server_default": True}
    )
    return compare_metadata(context, Base.metadata)


@pytest.mark.asyncio
async def test_models_match_migrations():
    async with test_engine.connect() as conn:
        diff = await conn.run_sync(_diff)
    assert diff == []
