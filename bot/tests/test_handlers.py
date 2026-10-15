from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.filters import CommandObject

from aroundfm_bot.api import (
    AlreadyLinkedError,
    BackendError,
    LinkExpiredError,
    NotLinkedError,
    NowPlaying,
    Station,
)
from aroundfm_bot.config import BotSettings
from aroundfm_bot.handlers import build_router
from aroundfm_bot.keyboards import app_url, main_keyboard


def settings(public_url: str = "https://aroundfm.example") -> BotSettings:
    return BotSettings(TELEGRAM_BOT_TOKEN="1:x", PUBLIC_URL=public_url, BOT_API_SECRET="s" * 32)


def handlers(api, public_url: str = "https://aroundfm.example") -> dict:
    router = build_router(settings(public_url), api)
    found = {h.callback.__name__: h.callback for h in router.message.handlers}
    found.update({h.callback.__name__: h.callback for h in router.callback_query.handlers})
    return found


def message(user_id: int = 7) -> MagicMock:
    msg = MagicMock()
    msg.answer = AsyncMock()
    msg.from_user = SimpleNamespace(id=user_id, username="neo", first_name="Neo", last_name=None)
    return msg


def text_of(msg: MagicMock) -> str:
    return msg.answer.await_args.args[0]


async def test_start_shows_mini_app_buttons():
    msg = message()
    await handlers(AsyncMock())["start"](msg)
    markup = msg.answer.await_args.kwargs["reply_markup"]
    assert markup.inline_keyboard[0][0].web_app.url == "https://aroundfm.example/"
    assert markup.inline_keyboard[1][0].web_app.url == "https://aroundfm.example/?vibe=focus"


def test_plain_links_without_https():
    markup = main_keyboard("http://localhost:3000", mini_app=False)
    assert markup.inline_keyboard[0][0].web_app is None
    assert markup.inline_keyboard[0][0].url == "http://localhost:3000/"


def test_app_url_encodes_params():
    assert app_url("https://x.io", station=3, vibe="focus") == "https://x.io/?station=3&vibe=focus"


async def test_deep_link_links_account():
    api = AsyncMock()
    api.link.return_value = "neo<script>"
    msg = message()
    await handlers(api)["start_with_payload"](
        msg, CommandObject(command="start", args="link_" + "a" * 43)
    )
    api.link.assert_awaited_once_with("a" * 43, 7, "neo", "Neo", None)
    assert "neo&lt;script&gt;" in text_of(msg)


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (LinkExpiredError(), "устарела"),
        (AlreadyLinkedError(), "другому аккаунту"),
        (BackendError(), "недоступен"),
    ],
)
async def test_deep_link_errors(error, expected):
    api = AsyncMock()
    api.link.side_effect = error
    msg = message()
    await handlers(api)["start_with_payload"](msg, CommandObject(command="start", args="link_x"))
    assert expected in text_of(msg)


async def test_unknown_deep_link_falls_back_to_start():
    api = AsyncMock()
    msg = message()
    await handlers(api)["start_with_payload"](msg, CommandObject(command="start", args="promo"))
    api.link.assert_not_called()
    assert "AroundFM" in text_of(msg)


async def test_now_callback_renders_station():
    api = AsyncMock()
    api.now_playing.return_value = NowPlaying(
        station=Station(id=3, name="Café <FM>", country="FR"),
        artist="Air",
        title="La femme d'argent",
        spotify_url="https://open.spotify.com/search/air",
    )
    callback = MagicMock(data="now:focus", answer=AsyncMock())
    callback.message.answer = AsyncMock()
    await handlers(api)["now_vibe"](callback)
    text = callback.message.answer.await_args.args[0]
    assert "Café &lt;FM&gt;" in text
    assert "Air — La femme d&#x27;argent" in text
    markup = callback.message.answer.await_args.kwargs["reply_markup"]
    assert markup.inline_keyboard[0][0].web_app.url.endswith("?station=3&vibe=focus")
    assert markup.inline_keyboard[1][0].url == "https://open.spotify.com/search/air"


async def test_now_callback_rejects_unknown_vibe():
    api = AsyncMock()
    callback = MagicMock(data="now:evil", answer=AsyncMock())
    await handlers(api)["now_vibe"](callback)
    api.now_playing.assert_not_called()


async def test_now_callback_backend_error():
    api = AsyncMock()
    api.now_playing.side_effect = BackendError()
    callback = MagicMock(data="now:focus", answer=AsyncMock())
    await handlers(api)["now_vibe"](callback)
    assert callback.answer.await_args.kwargs["show_alert"] is True


async def test_now_callback_empty():
    api = AsyncMock()
    api.now_playing.return_value = None
    callback = MagicMock(data="now:party", answer=AsyncMock())
    callback.message.answer = AsyncMock()
    await handlers(api)["now_vibe"](callback)
    assert "нет" in callback.message.answer.await_args.args[0]


async def test_favorites_list_is_truncated():
    api = AsyncMock()
    api.favorites.return_value = [Station(id=i, name=f"S{i}", country="X") for i in range(20)]
    msg = message()
    await handlers(api)["favorites"](msg)
    assert "…и ещё 5" in text_of(msg)


@pytest.mark.parametrize(
    ("result", "expected"),
    [(NotLinkedError(), "Привязать Telegram"), (BackendError(), "недоступен"), ([], "пусто")],
)
async def test_favorites_states(result, expected):
    api = AsyncMock()
    if isinstance(result, Exception):
        api.favorites.side_effect = result
    else:
        api.favorites.return_value = result
    msg = message()
    await handlers(api)["favorites"](msg)
    assert expected in text_of(msg)


@pytest.mark.parametrize("name", ["help_", "link_help", "now", "radio"])
async def test_simple_commands_answer(name):
    msg = message()
    await handlers(AsyncMock())[name](msg)
    msg.answer.assert_awaited_once()
