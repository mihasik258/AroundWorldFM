# AroundWorldFM

Радиостанции со всего мира на 3D-глобусе: смахните планету — заиграет ближайшая станция. Около 2000 проверенных музыкальных станций без новостей и разговоров, подборки по настроению, избранное и Telegram Mini App.

[![CI](https://github.com/mihasik258/AroundWorldFM/actions/workflows/ci.yml/badge.svg)](https://github.com/mihasik258/AroundWorldFM/actions/workflows/ci.yml)

## Возможности

- **Глобус.** Вращение с инерцией; после остановки включается ближайшая к центру станция. День и ночь по реальному положению солнца.
- **Настроения.** Фокус, драйв, утренний чай, вечеринка, закат, мировое турне; автосмена станции раз в пять минут, фильтр языков.
- **Что играет.** Текущий трек из ICY-метаданных потока и ссылка «Найти в Spotify».
- **Аккаунт.** Вход по паролю или через Telegram, оба способа можно привязать к одному аккаунту. Избранное, управление сессиями на устройствах, удаление аккаунта.
- **Telegram.** Бот открывает сайт как Mini App с автоматическим входом, показывает, что играет сейчас, и избранное привязанного аккаунта.
- **Администрирование.** Станции, статистика, проверка доступности потоков — вручную и по расписанию.

## Архитектура

```
             ┌──────────── Caddy: TLS, HSTS, HTTP/3 (только продакшен)
             ▼
Браузер ──▶ nginx ──▶ FastAPI ──▶ PostgreSQL 16
 / Mini App   │ статика,  │ async SQLAlchemy 2, Alembic
              │ CSP,      └──▶ радиопотоки (прокси, now-playing, проверка)
              │ лимиты
              │
Telegram ──▶ бот (aiogram 3) ──▶ FastAPI /internal
```

| Компонент | Стек |
|---|---|
| [backend](backend) | Python 3.12, FastAPI, SQLAlchemy 2 (async, asyncpg), Alembic, Pydantic 2, PyJWT, bcrypt, httpx |
| [frontend](frontend) | React 18, TypeScript (strict), Vite, Three.js, Tailwind |
| [bot](bot) | aiogram 3, httpx |
| Инфраструктура | Docker Compose, nginx (unprivileged), Caddy, GitHub Actions, Dependabot |

Подробности: [API](docs/api.md), [развёртывание](docs/deploy.md), [безопасность](SECURITY.md), [изменения](CHANGELOG.md).

## Быстрый старт

Нужны Docker с Compose v2, GNU Make и OpenSSL. Порты 3000, 8000 и 5432 должны быть свободны.

```bash
make up
```

Команда создаёт `.env` со случайными секретами (если его ещё нет), собирает образы, применяет миграции, загружает каталог станций и демо-пользователей.

- Сайт: http://localhost:3000
- Swagger UI: http://localhost:8000/docs
- Readiness: http://localhost:8000/health/ready

Демо-пользователи (только при `SEED_DEMO_USERS=true`, в продакшене запрещено):

| Роль | Логин | Пароль |
|---|---|---|
| admin | `admin` | `Admin12345!` |
| user | `listener` | `User12345!` |

Бот запускается отдельно, после того как в `.env` заполнен `TELEGRAM_BOT_TOKEN`:

```bash
docker compose --profile bot up -d
```

Без доступного по HTTPS адреса кнопки бота ведут на сайт обычными ссылками, а не как Mini App — это ограничение Telegram.

## Разработка без Docker

**Backend** — нужен PostgreSQL 16 с базой `aroundfm`.

```bash
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
sed -i "s/^SECRET_KEY=.*/SECRET_KEY=\"$(openssl rand -hex 32)\"/; s/^SECRET_PEPPER=.*/SECRET_PEPPER=\"$(openssl rand -hex 32)\"/" .env
alembic upgrade head
python -m app.cli seed
uvicorn app.main:app --reload
```

**Frontend** — Node.js 20.19+.

```bash
cd frontend
npm ci
npm run dev
```

Vite поднимается на http://localhost:5173 и проксирует `/api` на `http://127.0.0.1:8000`.

**Bot**

```bash
cd bot
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
python -m aroundfm_bot
```

**Управление**

```bash
python -m app.cli seed
python -m app.cli create-admin --username admin --email admin@example.com
python -m app.cli check-streams
python -m app.cli import-stations --dry-run
python -m app.cli import-stations --continents AF,SA --verify
alembic revision --autogenerate -m "describe change"
```

`seed` загружает каталог станций и маршруты, если таблицы пусты, а при `SEED_DEMO_USERS=true` — и демо-пользователей. `create-admin` берёт пароль из `ADMIN_PASSWORD` или спрашивает его.

`import-stations` добирает станции из [Radio Browser](https://www.radio-browser.info) — по одному запросу на страну, с паузой между запросами. Отбор:
- только HTTPS: такие потоки браузер играет напрямую, мимо сервера;
- кодек MP3 или AAC, не HLS, битрейт от 48 кбит/с;
- музыка под одно из настроений, без новостей, спорта и проповедей.

Лимит на страну растёт с её площадью: у Мальты 3 станции, у Германии 21, у США 110, максимум 120. В странах, где станций меньше половины лимита, принимаются и станции без жанровых тегов — они идут в «Мировое турне». Станции без собственных координат ставятся рядом со столицей, и плеер показывает у них только страну. Новые станции попадают в эфир после первой успешной проверки потока; `--verify` проверяет их сразу, иначе это сделает фоновая проверка. `--dry-run` показывает, что будет добавлено, ничего не сохраняя. Команды Make: `make import-stations` локально и `make prod-import` на сервере, параметры передаются через `ARGS="--continents AF"`.

## Проверки качества

```bash
make test
```

| Часть | Что проверяется |
|---|---|
| backend | ruff (включая bandit-правила), ruff format, mypy, pytest на реальном PostgreSQL, покрытие ≥ 85%, согласованность моделей и миграций |
| bot | ruff, mypy, pytest, покрытие ≥ 85% |
| frontend | ESLint без предупреждений, `tsc --noEmit`, Vitest с покрытием, production-сборка |

В CI дополнительно запускаются `alembic upgrade → check → downgrade`, `pip-audit`, `npm audit` для рантайм-зависимостей и сборка всех Docker-образов.

Тестам бэкенда нужна база `aroundfm_test`: `make test-backend` создаёт её сам; локально — `TEST_DATABASE_URL`. Схема накатывается миграциями и откатывается после прогона.

## Конфигурация

Все параметры задаются переменными окружения; полный список — в [`backend/app/core/config.py`](backend/app/core/config.py), примеры — в [`.env.example`](.env.example).

| Переменная | Назначение |
|---|---|
| `SECRET_KEY`, `SECRET_PEPPER` | Подпись JWT и перец для паролей, ≥ 32 байт, обязательны |
| `ENVIRONMENT` | `development` / `production`; в продакшене включаются защитные проверки и отключается Swagger |
| `PUBLIC_URL` | Публичный адрес сайта; из него строятся ссылки бота |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_USERNAME`, `BOT_API_SECRET` | Telegram: вход из Mini App, привязка, внутренний API бота |
| `SEED_DEMO_USERS` | Создавать демо-пользователей при сиде |
| `STREAM_CHECK_*` | Расписание и параллельность проверки потоков |
| `LOG_LEVEL`, `LOG_JSON` | Уровень и формат логов |

## Данные

- Станции: [Radio Browser](https://www.radio-browser.info), открытая база радиостанций.
- Площади стран и координаты столиц: [GeoNames](https://www.geonames.org), лицензия [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
- Погода в плеере: [Open-Meteo](https://open-meteo.com).

## Структура

```
backend/
  app/
    api/v1/        роуты: auth, users, stations, admin, flights, internal
    core/          настройки, безопасность, SSRF-защита, логи, фоновые задачи
    models/        ORM-модели
    schemas/       Pydantic-схемы
    services/      бизнес-логика: аккаунты, Telegram, каталог, проверка потоков
    cli.py         seed, create-admin, check-streams
  migrations/      Alembic
  tests/
bot/aroundfm_bot/  Telegram-бот
frontend/src/      React-приложение
deploy/            Caddyfile, скрипт бэкапов
docs/              API, развёртывание, диаграмма БД
```
