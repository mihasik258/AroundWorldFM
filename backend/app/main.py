import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1 import api_router
from app.core.config import settings
from app.core.jobs import LOCK_SESSION_CLEANUP, LOCK_STREAM_CHECK, periodic, session_job
from app.core.logging import configure_logging, request_id_var
from app.core.middleware import RequestContextMiddleware
from app.core.rate_limit import limiter
from app.db.session import AsyncSessionLocal, engine
from app.services.auth_service import AuthService
from app.services.identity_service import cleanup_flows
from app.services.stream_checker import run_due_stream_checks

configure_logging(settings.LOG_LEVEL, settings.LOG_JSON)
logger = logging.getLogger("aroundfm")

STREAM_CHECK_INITIAL_DELAY = 60


async def cleanup_expired(db: AsyncSession) -> None:
    sessions = await AuthService.cleanup_sessions(db)
    flows = await cleanup_flows(db)
    if sessions or flows:
        logger.info("Cleanup removed %d sessions and %d auth flows", sessions, flows)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info(
        "Starting %s %s (%s)", settings.PROJECT_NAME, settings.VERSION, settings.ENVIRONMENT
    )
    tasks = [
        asyncio.create_task(
            periodic(
                "session-cleanup",
                LOCK_SESSION_CLEANUP,
                settings.SESSION_CLEANUP_INTERVAL_SECONDS,
                session_job(cleanup_expired),
            )
        )
    ]
    if settings.STREAM_CHECK_ENABLED:
        tasks.append(
            asyncio.create_task(
                periodic(
                    "stream-check",
                    LOCK_STREAM_CHECK,
                    settings.STREAM_CHECK_INTERVAL_SECONDS,
                    session_job(run_due_stream_checks),
                    initial_delay=STREAM_CHECK_INITIAL_DELAY,
                )
            )
        )

    yield

    for task in tasks:
        task.cancel()
    for task in tasks:
        with contextlib.suppress(asyncio.CancelledError):
            await task
    await engine.dispose()
    logger.info("Shutdown complete")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="AroundFM REST API",
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
    openapi_url=None if settings.is_production else "/openapi.json",
    lifespan=lifespan,
)

app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> Response:
    return _rate_limit_exceeded_handler(request, exc)


_FRIENDLY_ERRORS = {
    ("string_pattern_mismatch", "username"): "Недопустимые символы в имени пользователя",
    ("string_too_short", "username"): "Имя пользователя короче 3 символов",
}


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors: list[str] = []
    for err in exc.errors():
        field = ".".join(str(x) for x in err.get("loc", []) if x not in ("body", "query", "path"))
        err_type = err.get("type", "")
        if (err_type, field) in _FRIENDLY_ERRORS:
            errors.append(_FRIENDLY_ERRORS[(err_type, field)])
        elif err_type == "string_too_short" and field in ("password", "new_password"):
            errors.append(f"Пароль короче {err.get('ctx', {}).get('min_length', 8)} символов")
        elif err_type == "value_error" and "email" in field:
            errors.append("Некорректный email")
        else:
            errors.append(f"{field}: {err.get('msg', '')}" if field else err.get("msg", ""))
    return JSONResponse(
        status_code=422,
        content={
            "detail": "; ".join(errors) or "Ошибка во входных данных",
            "validation_errors": [
                {"loc": e.get("loc"), "type": e.get("type"), "msg": e.get("msg")}
                for e in exc.errors()
            ],
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Внутренняя ошибка сервера", "request_id": request_id_var.get()},
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)
app.add_middleware(RequestContextMiddleware)


@app.get("/health", tags=["Система"], summary="Liveness")
async def health_live():
    return {"status": "ok", "version": settings.VERSION}


@app.get("/health/ready", tags=["Система"], summary="Readiness")
async def health_ready():
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Readiness check failed")
        return JSONResponse(status_code=503, content={"status": "unavailable"})
    return {"status": "ok", "version": settings.VERSION}


app.include_router(api_router, prefix=settings.API_V1_STR)
