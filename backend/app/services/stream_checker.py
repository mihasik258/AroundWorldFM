import asyncio
import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.station import StationStream, StreamHealth

UTC = timezone.utc
logger = logging.getLogger(__name__)


# Only network-level failures mean "this stream is down". Anything else (a bug in
# our own code, a missing setting) must propagate instead of silently marking every
# stream as dead — that once wiped the whole catalogue in two check runs.
STREAM_ERRORS = (httpx.HTTPError, asyncio.TimeoutError, OSError, ValueError)


async def check_single_stream(client: httpx.AsyncClient, stream_url: str) -> bool:
    """Tests if an audio stream URL is alive and responding with audio data."""
    try:
        # Try HEAD first
        try:
            resp = await client.head(
                stream_url, timeout=settings.STREAM_CHECK_TIMEOUT_SECONDS, follow_redirects=True
            )
            if resp.status_code in (200, 206):
                return True
        except STREAM_ERRORS:
            pass

        # If HEAD fails or is disallowed by stream server, test with partial streaming GET
        async with client.stream(
            "GET", stream_url, timeout=settings.STREAM_CHECK_TIMEOUT_SECONDS, follow_redirects=True
        ) as resp:
            if resp.status_code in (200, 206):
                # Read initial small chunk to confirm stream transmits data
                async for _ in resp.aiter_bytes(chunk_size=512):
                    return True
        return False
    except STREAM_ERRORS:
        return False


async def check_and_update_stream(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    stream: StationStream,
    db: AsyncSession,
) -> tuple[int, bool]:
    """Checks one station stream with concurrency limit and updates StreamHealth in DB."""
    async with semaphore:
        start_t = asyncio.get_event_loop().time()
        is_alive = await check_single_stream(client, stream.stream_url)
        duration_ms = int((asyncio.get_event_loop().time() - start_t) * 1000)

        health = stream.health
        if not health:
            health = StreamHealth(stream_id=stream.id)
            db.add(health)

        health.last_checked_at = datetime.now(UTC)
        health.response_time_ms = duration_ms if is_alive else None
        if is_alive:
            health.is_active = True
            health.check_fail_count = 0
        else:
            health.check_fail_count += 1
            if health.check_fail_count >= 2:
                health.is_active = False
                logger.warning(
                    f"Stream '{stream.stream_url}' marked inactive (fails: {health.check_fail_count})"
                )
        return stream.id, is_alive


async def run_stream_health_check(db: AsyncSession) -> None:
    """Runs a full sweep over all station streams, updating StreamHealth."""
    from sqlalchemy.orm import selectinload

    stmt = select(StationStream).options(selectinload(StationStream.health))
    result = await db.execute(stmt)
    streams = result.scalars().all()

    if not streams:
        return

    logger.info(f"Starting stream health check for {len(streams)} streams...")
    semaphore = asyncio.Semaphore(10)  # Max 10 concurrent requests
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; AroundFM-HealthCheck/2.0)",
        "Icy-MetaData": "1",
    }

    async with httpx.AsyncClient(headers=headers, trust_env=False) as client:
        tasks = [check_and_update_stream(client, semaphore, s, db) for s in streams]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    await db.commit()

    errors = [r for r in results if isinstance(r, BaseException)]
    if errors:
        # Surface unexpected failures instead of letting them look like dead streams
        logger.error(
            f"Health check hit {len(errors)} unexpected errors, first one: "
            f"{type(errors[0]).__name__}: {errors[0]}"
        )

    alive_count = sum(1 for r in results if isinstance(r, tuple) and r[1])
    logger.info(f"Health check finished: {alive_count}/{len(streams)} streams active.")
