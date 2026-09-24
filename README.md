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

```bash
docker-compose up --build
```

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
cp .env.example .env             # задать SECRET_KEY и SECRET_PEPPER
uvicorn app.main:app --reload --port 8000
```

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

Тестам нужна отдельная база `aroundfm_test` (адрес можно переопределить через `TEST_DATABASE_URL`).

```bash
cd backend
pytest -v
```

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
