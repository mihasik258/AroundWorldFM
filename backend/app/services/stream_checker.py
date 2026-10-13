import asyncio
import logging
import time
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import Select, and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.cache import catalog_cache
from app.core.config import settings
from app.core.net import UnsafeURLError, outbound_client
from app.models.station import StationStream, StreamHealth

logger = logging.getLogger(__name__)

FAILURES_BEFORE_INACTIVE = 2
STREAM_ERRORS = (httpx.HTTPError, asyncio.TimeoutError, OSError, UnsafeURLError)


async def check_single_stream(client: httpx.AsyncClient, stream_url: str) -> bool:
    try:
        async with client.stream("GET", stream_url) as resp:
            if resp.status_code not in (200, 206):
                return False
            async for chunk in resp.aiter_bytes(chunk_size=512):
                if chunk:
                    return True
        return False
    except STREAM_ERRORS:
        return False


async def _probe(
    client: httpx.AsyncClient, semaphore: asyncio.Semaphore, stream: StationStream
) -> tuple[StationStream, bool, int]:
    async with semaphore:
        started = time.perf_counter()
        alive = await check_single_stream(client, stream.stream_url)
        return stream, alive, int((time.perf_counter() - started) * 1000)


def _apply_result(db: AsyncSession, stream: StationStream, alive: bool, duration_ms: int) -> None:
    health = stream.health
    if health is None:
        health = StreamHealth(stream_id=stream.id, check_fail_count=0, is_active=True)
        db.add(health)
    health.last_checked_at = datetime.now(UTC)
    if alive:
        health.is_active = True
        health.check_fail_count = 0
        health.response_time_ms = duration_ms
    else:
        health.check_fail_count += 1
        health.response_time_ms = None
        if health.check_fail_count >= FAILURES_BEFORE_INACTIVE:
            health.is_active = False


def due_streams_query(batch_size: int, now: datetime) -> Select[tuple[StationStream]]:
    active_due = now - timedelta(hours=settings.STREAM_RECHECK_ACTIVE_HOURS)
    inactive_due = now - timedelta(hours=settings.STREAM_RECHECK_INACTIVE_HOURS)
    return (
        select(StationStream)
        .outerjoin(StreamHealth, StreamHealth.stream_id == StationStream.id)
        .options(selectinload(StationStream.health))
        .where(
            or_(
                StreamHealth.stream_id.is_(None),
                StreamHealth.last_checked_at.is_(None),
                and_(StreamHealth.is_active.is_(True), StreamHealth.last_checked_at < active_due),
                and_(
                    StreamHealth.is_active.is_(False), StreamHealth.last_checked_at < inactive_due
                ),
            )
        )
        .order_by(StreamHealth.last_checked_at.asc().nulls_first(), StationStream.id)
        .limit(batch_size)
    )


async def run_due_stream_checks(db: AsyncSession) -> dict[str, int]:
    stmt = due_streams_query(settings.STREAM_CHECK_BATCH_SIZE, datetime.now(UTC))
    streams = (await db.execute(stmt)).scalars().all()
    return await _check(db, list(streams))


async def run_stream_health_check(db: AsyncSession) -> dict[str, int]:
    streams = (
        (await db.execute(select(StationStream).options(selectinload(StationStream.health))))
        .scalars()
        .all()
    )
    return await _check(db, list(streams))


async def _check(db: AsyncSession, streams: list[StationStream]) -> dict[str, int]:
    if not streams:
        return {"checked": 0, "alive": 0}

    logger.info("Checking %d streams", len(streams))
    semaphore = asyncio.Semaphore(settings.STREAM_CHECK_CONCURRENCY)
    async with outbound_client(
        settings.STREAM_CHECK_TIMEOUT_SECONDS, headers={"Icy-MetaData": "0"}
    ) as client:
        results = await asyncio.gather(
            *(_probe(client, semaphore, s) for s in streams), return_exceptions=True
        )

    alive = 0
    for result in results:
        if isinstance(result, BaseException):
            logger.error("Stream probe crashed: %r", result)
            continue
        stream, ok, duration_ms = result
        alive += ok
        _apply_result(db, stream, ok, duration_ms)

    await db.commit()
    catalog_cache.clear()
    logger.info("Active streams: %d/%d", alive, len(streams))
    return {"checked": len(streams), "alive": alive}
