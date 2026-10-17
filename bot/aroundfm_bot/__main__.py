import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, MenuButtonWebApp, WebAppInfo

from aroundfm_bot.api import BackendClient
from aroundfm_bot.config import BotSettings
from aroundfm_bot.handlers import build_router
from aroundfm_bot.keyboards import app_url

COMMANDS = [
    BotCommand(command="start", description="Открыть приложение"),
    BotCommand(command="now", description="Что играет сейчас"),
    BotCommand(command="favorites", description="Избранное"),
    BotCommand(command="link", description="Привязать аккаунт"),
    BotCommand(command="help", description="Справка"),
]


async def main() -> None:
    settings = BotSettings()
    logging.basicConfig(
        level=settings.LOG_LEVEL.upper(),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    bot = Bot(settings.TELEGRAM_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    api = BackendClient(settings.BACKEND_URL, settings.BOT_API_SECRET)
    dispatcher = Dispatcher()
    dispatcher.include_router(build_router(settings, api))

    await bot.set_my_commands(COMMANDS)
    if settings.mini_app_supported:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="Радио", web_app=WebAppInfo(url=app_url(settings.PUBLIC_URL))
            )
        )
    try:
        await dispatcher.start_polling(bot, allowed_updates=dispatcher.resolve_used_update_types())
    finally:
        await api.aclose()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
