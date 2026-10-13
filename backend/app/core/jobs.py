import asyncio
import logging
from collections.abc import Awaitable, Callable

from sqlalchemy import text

from app.db.session import AsyncSessionLocal, engine

logger = logging.getLogger(__name__)

LOCK_SESSION_CLEANUP = 7_301_001
LOCK_STREAM_CHECK = 7_301_002


async def run_exclusive(lock_id: int, job: Callable[[], Awaitable[None]]) -> bool:
    async with engine.connect() as conn:
        acquired = (
            await conn.execute(text("SELECT pg_try_advisory_lock(:id)"), {"id": lock_id})
        ).scalar_one()
        if not acquired:
            return False
        try:
            await job()
        finally:
            await conn.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": lock_id})
    return True


async def periodic(
    name: str,
    lock_id: int,
    interval: float,
    job: Callable[[], Awaitable[None]],
    initial_delay: float = 0,
) -> None:
    await asyncio.sleep(initial_delay)
    while True:
        try:
            ran = await run_exclusive(lock_id, job)
            if not ran:
                logger.debug("Job %s skipped, lock held elsewhere", name)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Job %s failed", name)
        await asyncio.sleep(interval)


def session_job(func: Callable) -> Callable[[], Awaitable[None]]:
    async def runner() -> None:
        async with AsyncSessionLocal() as db:
            await func(db)

    return runner
