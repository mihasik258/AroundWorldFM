import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.v1 import api_router
from app.core.config import settings
from app.core.rate_limit import limiter
from app.db.base import Base
from app.db.session import AsyncSessionLocal, engine
from app.services.seed_service import seed_initial_data
from app.services.stream_checker import run_stream_health_check

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("aroundfm")


async def periodic_stream_checker():
    logger.info("Background stream checker task started.")
    try:
        while True:
            await asyncio.sleep(settings.STREAM_CHECK_INTERVAL_SECONDS)
            async with AsyncSessionLocal() as db:
                try:
                    await run_stream_health_check(db)
                except Exception as e:
                    logger.error(f"Error during scheduled stream check: {e}")
    except asyncio.CancelledError:
        logger.info("Background stream checker task cancelled.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup"""
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION}...")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        await seed_initial_data(db)

    checker_task = asyncio.create_task(periodic_stream_checker())

    yield

    logger.info("Shutting down...")
    checker_task.cancel()
    try:
        await checker_task
    except asyncio.CancelledError:
        pass
    await engine.dispose()
    logger.info("Database engine disposed. Shutdown complete.")


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
            friendly = "Имя пользователя может содержать только латинские буквы, цифры, '_' и '-'"
        elif "string_too_short" in err_type and field == "password":
            min_l = err.get("ctx", {}).get("min_length", 8)
            friendly = f"Пароль должен содержать минимум {min_l} символов"
        elif "string_too_short" in err_type and field == "username":
            friendly = "Имя пользователя должно быть не короче 3 символов"
        elif "value_error" in err_type and "email" in field:
            friendly = "Некорректный адрес электронной почты"
        else:
            friendly = f"{field}: {msg}" if field else msg
        errors.append(friendly)

    formatted_msg = "; ".join(errors) if errors else "Ошибка в входных данных"
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


@app.get("/health", tags=["Система"], summary="Проверка состояния сервера")
async def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
    }


app.include_router(api_router, prefix=settings.API_V1_STR)
