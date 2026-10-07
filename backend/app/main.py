import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

from app.api.v1 import api_router
from app.core.config import settings
from app.core.rate_limit import limiter
from app.db.base import Base
from app.db.session import AsyncSessionLocal, engine
from app.services.auth_service import AuthService
from app.services.flight_service import FlightService
from app.services.seed_service import seed_initial_data

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("aroundfm")


async def periodic_session_cleanup():
    while True:
        try:
            async with AsyncSessionLocal() as db:
                removed = await AuthService.cleanup_sessions(db)
            if removed:
                logger.info(f"Removed {removed} sessions")
        except Exception as e:
            logger.error(f"Session cleanup failed: {e}")
        await asyncio.sleep(settings.SESSION_CLEANUP_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.PROJECT_NAME} {settings.VERSION}")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        await seed_initial_data(db)
        await FlightService.seed_flight_data(db)

    cleanup_task = asyncio.create_task(periodic_session_cleanup())

    yield

    logger.info("Shutting down")
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    await engine.dispose()
    logger.info("Shutdown complete")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="AroundFM REST API",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors: list[str] = []
    for err in exc.errors():
        loc_parts = [str(x) for x in err.get("loc", []) if x not in ("body", "query")]
        field = ".".join(loc_parts)
        err_type = err.get("type", "")
        msg = err.get("msg", "")

        if "string_pattern_mismatch" in err_type and field == "username":
            friendly = "Недопустимые символы в имени пользователя"
        elif "string_too_short" in err_type and field == "password":
            min_l = err.get("ctx", {}).get("min_length", 8)
            friendly = f"Пароль короче {min_l} символов"
        elif "string_too_short" in err_type and field == "username":
            friendly = "Имя пользователя короче 3 символов"
        elif "value_error" in err_type and "email" in field:
            friendly = "Некорректный email"
        else:
            friendly = f"{field}: {msg}" if field else msg
        errors.append(friendly)

    formatted_msg = "; ".join(errors) if errors else "Ошибка во входных данных"
    return JSONResponse(
        status_code=422,
        content={"detail": formatted_msg, "validation_errors": exc.errors()},
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["Система"], summary="Состояние сервера")
async def health_check():
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "database": f"error: {e}",
                "service": settings.PROJECT_NAME,
                "version": settings.VERSION,
            },
        )
    return {
        "status": "healthy",
        "database": "connected",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
    }


app.include_router(api_router, prefix=settings.API_V1_STR)
