import hmac

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.config import settings
from app.schemas.internal import TelegramLinkRequest, TelegramLinkResult
from app.schemas.station import StationRead
from app.services.telegram_service import TelegramService, TelegramUser


async def require_bot(x_bot_secret: str | None = Header(None)) -> None:
    expected = settings.BOT_API_SECRET
    if not expected or not x_bot_secret or not hmac.compare_digest(x_bot_secret, expected):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")


router = APIRouter(
    prefix="/internal/telegram",
    tags=["Internal"],
    include_in_schema=False,
    dependencies=[Depends(require_bot)],
)


@router.post("/link", response_model=TelegramLinkResult)
async def complete_link(payload: TelegramLinkRequest, db: AsyncSession = Depends(get_db)):
    user = await TelegramService.complete_link(
        db,
        payload.token,
        TelegramUser(
            id=payload.telegram_id,
            username=payload.username,
            first_name=payload.first_name,
            last_name=payload.last_name,
        ),
    )
    return TelegramLinkResult(username=user.username)


@router.get("/users/{telegram_id}/favorites", response_model=list[StationRead])
async def favorites(telegram_id: int, db: AsyncSession = Depends(get_db)):
    return await TelegramService.favorites(db, telegram_id)
