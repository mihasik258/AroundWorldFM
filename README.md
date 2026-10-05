# AroundWorldFM

Веб-приложение для прослушивания радиостанций со всего мира: станции отображаются на 3D-глобусе, их можно включать прямо с карты.

## Стек

- Backend: Python 3.12, FastAPI, SQLAlchemy 2.0 (async), PostgreSQL 16
- Frontend: Vite, React, TypeScript, Tailwind CSS
- Безопасность: bcrypt (соль + секретный перец), JWT (access 15 мин / refresh 30 дней), rate limiting через slowapi

## Текущий статус — этап 1 (базовый сценарий)

- архитектура backend / frontend, docker-compose
- модели данных: пользователи, способы входа, сессии, станции, потоки, избранное
- регистрация и вход по логину/email и паролю
- обновление access-токена по refresh-токену, просмотр и отзыв сессий
- сквозной сценарий: регистрация → вход → глобус со станциями → воспроизведение

## Запуск через Docker Compose

Нужны Docker с Compose v2 и OpenSSL. Порты 3000, 8000 и 5432 должны быть свободны.

```bash
printf "SECRET_KEY=%s\nSECRET_PEPPER=%s\n" "$(openssl rand -hex 32)" "$(openssl rand -hex 32)" > .env
docker compose up --build
```

Первая команда создаёт в корне репозитория `.env` с ключом подписи JWT и перцем для паролей. Без него compose не запустится, в git файл не попадает.

- Web-интерфейс: http://localhost:3000
- Swagger UI: http://localhost:8000/docs
- Health check: http://localhost:8000/health

При старте бэкенд сам создаёт таблицы в БД и загружает демо-данные.

## Локальный запуск

### Backend

Нужен запущенный PostgreSQL 16 с базой `aroundfm`.

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
sed -i "s/^SECRET_KEY=.*/SECRET_KEY=\"$(openssl rand -hex 32)\"/; s/^SECRET_PEPPER=.*/SECRET_PEPPER=\"$(openssl rand -hex 32)\"/" .env
uvicorn app.main:app --reload --port 8000
```

`SECRET_KEY` и `SECRET_PEPPER` обязательны и должны быть не короче 32 байт, иначе приложение не стартует.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Dev-сервер поднимается на http://localhost:5173 и проксирует `/api` на `http://127.0.0.1:8000`.

## Демо-пользователи

| Роль  | Логин      | Пароль        |
|-------|------------|---------------|
| admin | `admin`    | `Admin12345!` |
| user  | `listener` | `User12345!`  |

## Тесты

Тестам нужна отдельная база `aroundfm_test`. Если запущен compose, создать её:

```bash
docker compose exec db psql -U postgres -c "CREATE DATABASE aroundfm_test;"
```

Тесты запускаются из окружения backend (см. «Локальный запуск»), секреты для них не нужны:

```bash
cd backend
pytest -v
```

По умолчанию тесты подключаются к `postgresql+asyncpg://postgres:postgrespassword@localhost:5432/aroundfm_test`. Другой адрес задаётся переменной `TEST_DATABASE_URL`. Таблицы тестовой базы создаются перед запуском и удаляются после него.

## Структура

```
backend/
  app/
    api/v1/         роуты: auth, users, stations, admin
    core/           настройки, JWT, хеширование паролей, rate limit
    db/             движок и сессия SQLAlchemy
    models/         ORM-модели
    schemas/        Pydantic-схемы
    services/       бизнес-логика
  tests/
frontend/
  src/
    api/            клиент REST API
    components/     глобус, плеер, модалки входа и сессий
    context/        AuthContext, PlayerContext
docs/               API и диаграмма БД
```
