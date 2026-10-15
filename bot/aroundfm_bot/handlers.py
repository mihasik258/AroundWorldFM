import html
import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import CallbackQuery, Message

from aroundfm_bot.api import (
    AlreadyLinkedError,
    BackendClient,
    BackendError,
    LinkExpiredError,
    NotLinkedError,
)
from aroundfm_bot.config import BotSettings
from aroundfm_bot.keyboards import VIBE_IDS, main_keyboard, now_keyboard, station_keyboard

logger = logging.getLogger(__name__)

LINK_PREFIX = "link_"
FAVORITES_LIMIT = 15

WELCOME = (
    "<b>AroundFM</b> — радиостанции со всего мира на 3D-глобусе.\n\n"
    "Выберите настроение или откройте приложение."
)
HELP = (
    "/start — открыть приложение\n"
    "/now — что играет сейчас\n"
    "/favorites — избранные станции\n"
    "/link — привязать аккаунт сайта\n"
    "/help — справка"
)
LINK_HOWTO = (
    "Чтобы привязать аккаунт: войдите на сайте, откройте «Аккаунт» и нажмите "
    "«Привязать Telegram». Ссылка вернёт вас сюда."
)
UNAVAILABLE = "Сервис временно недоступен, попробуйте позже."


def build_router(settings: BotSettings, api: BackendClient) -> Router:
    router = Router(name="aroundfm")
    mini_app = settings.mini_app_supported

    @router.message(CommandStart(deep_link=True))
    async def start_with_payload(message: Message, command: CommandObject) -> None:
        payload = command.args or ""
        if not payload.startswith(LINK_PREFIX) or message.from_user is None:
            await start(message)
            return
        user = message.from_user
        try:
            username = await api.link(
                payload[len(LINK_PREFIX) :],
                user.id,
                user.username,
                user.first_name,
                user.last_name,
            )
        except LinkExpiredError:
            await message.answer("Ссылка устарела. Создайте новую в настройках аккаунта.")
            return
        except AlreadyLinkedError:
            await message.answer("Этот Telegram уже привязан к другому аккаунту.")
            return
        except BackendError:
            logger.exception("Linking failed")
            await message.answer(UNAVAILABLE)
            return
        await message.answer(
            f"Готово: Telegram привязан к аккаунту <b>{html.escape(username)}</b>.",
            reply_markup=main_keyboard(settings.PUBLIC_URL, mini_app),
        )

    @router.message(CommandStart())
    async def start(message: Message) -> None:
        await message.answer(WELCOME, reply_markup=main_keyboard(settings.PUBLIC_URL, mini_app))

    @router.message(Command("radio", "vibes"))
    async def radio(message: Message) -> None:
        await message.answer(
            "Выберите настроение:", reply_markup=main_keyboard(settings.PUBLIC_URL, mini_app)
        )

    @router.message(Command("help"))
    async def help_(message: Message) -> None:
        await message.answer(HELP)

    @router.message(Command("link"))
    async def link_help(message: Message) -> None:
        await message.answer(LINK_HOWTO)

    @router.message(Command("now"))
    async def now(message: Message) -> None:
        await message.answer("Какое настроение?", reply_markup=now_keyboard())

    @router.callback_query(F.data.startswith("now:"))
    async def now_vibe(callback: CallbackQuery) -> None:
        vibe = (callback.data or "").removeprefix("now:")
        if vibe not in VIBE_IDS or callback.message is None:
            await callback.answer()
            return
        try:
            playing = await api.now_playing(vibe)
        except BackendError:
            logger.exception("Now playing failed")
            await callback.answer(UNAVAILABLE, show_alert=True)
            return
        await callback.answer()
        if playing is None:
            await callback.message.answer("Для этого настроения станций нет.")
            return
        lines = [
            f"<b>{html.escape(playing.station.name)}</b>",
            html.escape(playing.station.country),
        ]
        if playing.title:
            track = f"{playing.artist} — {playing.title}" if playing.artist else playing.title
            lines.append(f"Сейчас: {html.escape(track)}")
        await callback.message.answer(
            "\n".join(lines),
            reply_markup=station_keyboard(
                settings.PUBLIC_URL, mini_app, playing.station.id, vibe, playing.spotify_url
            ),
        )

    @router.message(Command("favorites"))
    async def favorites(message: Message) -> None:
        if message.from_user is None:
            return
        try:
            stations = await api.favorites(message.from_user.id)
        except NotLinkedError:
            await message.answer(LINK_HOWTO)
            return
        except BackendError:
            logger.exception("Favorites failed")
            await message.answer(UNAVAILABLE)
            return
        if not stations:
            await message.answer("В избранном пока пусто.")
            return
        lines = [
            f"• {html.escape(s.name)} — {html.escape(s.country)}"
            for s in stations[:FAVORITES_LIMIT]
        ]
        if len(stations) > FAVORITES_LIMIT:
            lines.append(f"…и ещё {len(stations) - FAVORITES_LIMIT}")
        await message.answer("<b>Избранное</b>\n" + "\n".join(lines))

    return router
