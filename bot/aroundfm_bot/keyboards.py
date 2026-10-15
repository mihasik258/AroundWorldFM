from urllib.parse import urlencode

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

VIBES: tuple[tuple[str, str], ...] = (
    ("focus", "Фокус"),
    ("night_drive", "Драйв"),
    ("coffee", "Утренний чай"),
    ("party", "Вечеринка"),
    ("sunset", "Закат"),
    ("world_odyssey", "Мировое турне"),
)
VIBE_IDS = frozenset(v for v, _ in VIBES)


def app_url(public_url: str, **params: str | int) -> str:
    query = urlencode(params)
    return f"{public_url}/?{query}" if query else f"{public_url}/"


def open_button(text: str, url: str, mini_app: bool) -> InlineKeyboardButton:
    if mini_app:
        return InlineKeyboardButton(text=text, web_app=WebAppInfo(url=url))
    return InlineKeyboardButton(text=text, url=url)


def _rows(buttons: list[InlineKeyboardButton], size: int = 2) -> list[list[InlineKeyboardButton]]:
    return [buttons[i : i + size] for i in range(0, len(buttons), size)]


def main_keyboard(public_url: str, mini_app: bool) -> InlineKeyboardMarkup:
    vibes = [open_button(label, app_url(public_url, vibe=v), mini_app) for v, label in VIBES]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [open_button("Открыть AroundFM", app_url(public_url), mini_app)],
            *_rows(vibes),
        ]
    )


def now_keyboard() -> InlineKeyboardMarkup:
    buttons = [InlineKeyboardButton(text=label, callback_data=f"now:{v}") for v, label in VIBES]
    return InlineKeyboardMarkup(inline_keyboard=_rows(buttons))


def station_keyboard(
    public_url: str, mini_app: bool, station_id: int, vibe: str, spotify_url: str | None
) -> InlineKeyboardMarkup:
    rows = [
        [
            open_button("Слушать", app_url(public_url, station=station_id, vibe=vibe), mini_app),
            InlineKeyboardButton(text="Ещё", callback_data=f"now:{vibe}"),
        ]
    ]
    if spotify_url:
        rows.append([InlineKeyboardButton(text="Найти в Spotify", url=spotify_url)])
    return InlineKeyboardMarkup(inline_keyboard=rows)
