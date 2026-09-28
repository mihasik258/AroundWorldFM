# AroundFM API — справочник эндпоинтов

Базовый префикс: `/api/v1` (настраивается через `API_V1_STR`).
Интерактивная документация доступна на работающем сервере: `/docs` (Swagger) и `/redoc`.

**Аутентификация.** Access-токен (JWT, 15 минут) передаётся в заголовке
`Authorization: Bearer <access_token>`. Refresh-токен (30 дней) выдаётся **только**
в httpOnly-cookie и в теле ответов не появляется никогда — подробности в разделе
[«Модель токенов»](#модель-токенов).

Обозначения в колонке «Доступ»:
- **—** — публичный эндпоинт, токен не нужен
- **USER** — нужен валидный access-токен
- **ADMIN** — нужен токен пользователя с ролью `admin`

---

## Сводная таблица

| Метод | Путь | Доступ | Назначение |
|---|---|---|---|
| GET | `/health` | — | Проверка состояния сервера |
| POST | `/api/v1/auth/register` | — | Регистрация |
| POST | `/api/v1/auth/login` | — | Вход, выдача пары токенов |
| POST | `/api/v1/auth/refresh` | cookie | Новый access-токен (с ротацией refresh) |
| POST | `/api/v1/auth/logout` | cookie | Выход с текущего устройства |
| GET | `/api/v1/auth/sessions` | USER | Список активных сессий |
| DELETE | `/api/v1/auth/sessions/{session_id}` | USER | Отзыв одной сессии |
| POST | `/api/v1/auth/sessions/revoke-all` | USER | Выход на всех **остальных** устройствах |
| GET | `/api/v1/users/me` | USER | Профиль текущего пользователя |
| POST | `/api/v1/users/me/change-password` | USER | Смена пароля |
| GET | `/api/v1/stations` | — | Список станций с фильтрами |
| GET | `/api/v1/stations/random` | — | Случайная работающая станция |
| GET | `/api/v1/stations/genres` | — | Все доступные жанры |
| GET | `/api/v1/stations/languages` | — | Все языки вещания |
| GET | `/api/v1/stations/vibe/list` | — | Список поддерживаемых вайбов |
| GET | `/api/v1/stations/vibe/next` | — | Следующая станция по вайбу |
| GET | `/api/v1/stations/vibe/stations` | — | Все станции вайба (для глобуса) |
| GET | `/api/v1/stations/vibe/languages` | — | Языки с количеством станций |
| GET | `/api/v1/stations/{station_id}/stream` | — | Проксирование аудиопотока |
| GET | `/api/v1/stations/{station_id}/now-playing` | — | Текущий трек (ICY-метаданные) |
| GET | `/api/v1/stations/favorites/my` | USER | Избранные станции |
| POST | `/api/v1/stations/favorites/{station_id}` | USER | Добавить в избранное |
| DELETE | `/api/v1/stations/favorites/{station_id}` | USER | Удалить из избранного |
| GET | `/api/v1/admin/stats` | ADMIN | Системная статистика |
| POST | `/api/v1/admin/stations` | ADMIN | Создать станцию |
| PATCH | `/api/v1/admin/stations/{station_id}` | ADMIN | Обновить станцию |
| DELETE | `/api/v1/admin/stations/{station_id}` | ADMIN | Удалить станцию |
| POST | `/api/v1/admin/trigger-stream-check` | ADMIN | Запустить проверку потоков |

Всего 28 эндпоинтов. «cookie» — нужен refresh-cookie, access-токен не требуется.

---

## Система

### `GET /health`
Проверка живости сервиса. Токен не требуется.

```json
{ "status": "healthy", "database": "connected", "service": "AroundFM API", "version": "2.0.0" }
```
Пингует базу запросом `SELECT 1`; если она недоступна — `503` и `"status": "unhealthy"`.

---

## Аутентификация и безопасность

### `POST /api/v1/auth/register` → `201`
Регистрация. Ограничение частоты: **5 запросов в минуту** с одного IP.

Тело запроса:
```json
{ "email": "user@example.com", "username": "myuser", "password": "MyPass123!" }
```
Правила: `username` 3–32 символа, только `a-z A-Z 0-9 _ -`; `password` минимум 8 символов; `email` — валидный адрес.

Ответ — профиль пользователя (`UserRead`), пароль и его хэш никогда не возвращаются:
```json
{ "id": 3, "username": "myuser", "email": "user@example.com",
  "role": "user", "is_active": true,
  "created_at": "2026-09-23T10:00:00Z", "auth_providers": ["password"] }
```

Ошибки: `400` — email или username уже заняты; `422` — нарушены правила валидации (сообщения на русском); `429` — превышен лимит запросов.

### `POST /api/v1/auth/login` → `200`
Вход. Ограничение частоты: **10 запросов в минуту** с одного IP — защита от перебора паролей.

Поле `login` принимает **либо** username, **либо** email:
```json
{ "login": "myuser", "password": "MyPass123!" }
```

Ответ — только access-токен:
```json
{ "access_token": "eyJ...", "token_type": "bearer",
  "expires_in": 900, "user_id": 3, "username": "myuser", "role": "user" }
```
Refresh-токен приходит в заголовке:
```
Set-Cookie: refresh_token=eyJ...; HttpOnly; Secure; SameSite=strict; Path=/api/v1/auth; Max-Age=2592000
```
Побочный эффект: создаётся запись в `user_sessions` — сохраняется SHA-256 хэш refresh-токена, IP, User-Agent и распознанное имя устройства. Идентификатор этой сессии записывается в access-токен (claim `sid`).

Ошибки: `401` — неверные данные; `403` — учётная запись отключена; `429` — превышен лимит.

### `POST /api/v1/auth/refresh` → `200`
Новый access-токен. Тела у запроса нет — браузер сам прикладывает refresh-cookie.
Проверяется подпись JWT и состояние сессии в БД. Каждый вызов **ротирует** refresh-токен: в ответе приходит новая cookie, старая перестаёт действовать.

| Что пришло | Результат |
|---|---|
| Текущий refresh-токен | `200`, новый access-токен и новая cookie |
| Только что заменённый токен, в пределах 30 секунд после ротации | `200`, новый access-токен, cookie **не** меняется — это гонка двух вкладок, а не атака |
| Заменённый токен, позже 30 секунд | `401`, **вся сессия отзывается** — токен был скопирован |
| Нет cookie, сессия отозвана или истекла | `401` |

Срок жизни сессии абсолютный: ротация не продлевает 30 дней с момента входа. Окно для гонки задаётся `REFRESH_REUSE_GRACE_SECONDS`.

### `POST /api/v1/auth/logout` → `200`
Отзывает сессию, которой принадлежит refresh-cookie, и удаляет cookie. Access-токен не нужен, чтобы выход работал и после его истечения. Без cookie тоже отвечает `200`: вызов безопасно повторять.

### `GET /api/v1/auth/sessions` → `200` — USER
Список активных сессий (не отозванных и не истёкших), свежие первыми. Сессия, с которой сделан запрос, помечена `is_current: true`:
```json
[ { "id": 5, "ip_address": "203.0.113.7", "device_name": "Windows PC",
    "user_agent": "Mozilla/5.0 ...",
    "created_at": "...", "last_used_at": "...", "is_current": true } ]
```

### `DELETE /api/v1/auth/sessions/{session_id}` → `200` — USER
Отзыв конкретной сессии. Действует **сразу**: access-токены этой сессии перестают приниматься на следующем же запросе. `404`, если сессия не найдена или уже отозвана. Чужую сессию отозвать нельзя. Отзыв текущей сессии равносилен выходу — ответ удаляет refresh-cookie.

### `POST /api/v1/auth/sessions/revoke-all` → `200` — USER
Выход на всех **остальных** устройствах, текущая сессия сохраняется. Ответ: `{ "status": "ok", "message": "Отозвано сессий на других устройствах: 3" }`.

---

## Пользователи

### `GET /api/v1/users/me` → `200` — USER
Профиль текущего пользователя (`UserRead`, см. ответ регистрации).

### `POST /api/v1/users/me/change-password` → `200` — USER
```json
{ "old_password": "MyPass123!", "new_password": "NewPass456!" }
```
Проверяется старый пароль. После успешной смены **отзываются все сессии, включая текущую**, а ответ удаляет refresh-cookie — требуется повторный вход на всех устройствах.

Ошибки: `400` — старый пароль неверен либо у учётной записи нет пароля (вход только через внешнего провайдера).

---

## Радиостанции

### `GET /api/v1/stations` → `200`
Список станций с фильтрацией. Все параметры необязательны.

| Параметр | Тип | По умолчанию | Описание |
|---|---|---|---|
| `genres` | string | — | Жанры через запятую (`jazz,rock`); `any` — без фильтра |
| `languages` | string | — | Языки через запятую |
| `country` | string | — | Страна (поиск по подстроке) |
| `search` | string | — | Поиск по названию или стране |
| `limit` | int | 50 | 1–3000 |
| `offset` | int | 0 | Смещение для постраничного вывода |

Возвращаются только станции с активным основным потоком. Фильтр по жанрам использует пересечение массивов PostgreSQL (`&&`) по GIN-индексу на `stations.tags`.

Формат элемента (`StationRead`):
```json
{ "id": 1, "station_uuid": null, "name": "FIP Radio",
  "stream_url": "https://icecast.radiofrance.fr/fip-midfi.mp3",
  "homepage_url": "https://www.radiofrance.fr/fip", "favicon_url": null,
  "country": "France", "country_code": "FR",
  "latitude": 48.8566, "longitude": 2.3522, "language": "french",
  "tags": ["eclectic", "jazz", "world"], "codec": "MP3", "bitrate": 128,
  "is_active": true, "last_checked_at": "2026-09-23T12:20:00Z",
  "created_at": "...", "updated_at": "...",
  "streams": [ { "id": 1, "stream_url": "...", "codec": "MP3", "bitrate": 128,
                 "is_primary": true, "is_active": true, "response_time_ms": 320 } ] }
```
Поля `stream_url`, `codec`, `bitrate` на верхнем уровне — это данные **основного** потока, продублированные для удобства клиента; полный перечень потоков лежит в `streams[]`.

### `GET /api/v1/stations/random` → `200`
Случайная активная станция. Параметры: `genres`, `languages` (через запятую). `404`, если под критерии ничего не подошло.

### `GET /api/v1/stations/genres` → `200`
Отсортированный список уникальных жанров (`["ambient", "jazz", ...]`). Собирается через `unnest(tags)`.

### `GET /api/v1/stations/languages` → `200`
Отсортированный список языков активных станций.

---

## Вайбы (тематические подборки)

Вайб — это curated-набор жанров с положительными и отрицательными ключевыми словами. Поддерживаются: `focus`, `night_drive`, `coffee`, `party`, `sunset`, `world_odyssey`. Из всех подборок исключаются разговорные/новостные станции.

### `GET /api/v1/stations/vibe/list` → `200`
```json
[ { "id": "focus", "label": "Deep Focus" }, { "id": "night_drive", "label": "Night Drive" } ]
```

### `GET /api/v1/stations/vibe/next` → `200`
Следующая станция в рамках вайба.

| Параметр | По умолчанию | Описание |
|---|---|---|
| `vibe` | `focus` | Идентификатор вайба |
| `exclude_languages` | — | Языки-исключения через запятую |
| `exclude_ids` | — | ID недавно прослушанных станций через запятую |

Если под исключениями не осталось кандидатов, фильтр по `exclude_ids` сбрасывается (чтобы подборка не «заканчивалась»). `404` — подходящих станций нет вовсе.

### `GET /api/v1/stations/vibe/stations` → `200`
Все станции вайба, у которых заданы координаты — для отображения на глобусе. Параметры: `vibe`, `exclude_languages`.

### `GET /api/v1/stations/vibe/languages` → `200`
Языки с количеством станций, по убыванию:
```json
[ { "code": "english", "name": "English", "count": 412 } ]
```

---

## Воспроизведение

### `GET /api/v1/stations/{station_id}/stream`
Проксирование аудиопотока (`audio/mpeg`, потоковая отдача). Нужно, чтобы обойти CORS-ограничения и блокировки провайдеров при воспроизведении в браузере. `404` — станция или поток не найдены.

### `GET /api/v1/stations/{station_id}/now-playing` → `200`
Текущий трек из ICY-метаданных потока. Результат кэшируется в памяти на 20 секунд.
```json
{ "station_id": 1, "has_track": true, "raw_title": "Miles Davis - So What",
  "artist": "Miles Davis", "title": "So What",
  "spotify_url": "https://open.spotify.com/search/Miles%20Davis%20So%20What" }
```
Если станция не передаёт метаданные, `has_track` будет `false`, остальные поля — `null`.

---

## Избранное

### `GET /api/v1/stations/favorites/my` → `200` — USER
Избранные станции пользователя (формат `StationRead`), недавно добавленные первыми.

### `POST /api/v1/stations/favorites/{station_id}` → `200` — USER
Добавление в избранное. Повторное добавление не создаёт дубликат (на уровне БД стоит `UNIQUE(user_id, station_id)`) и возвращает `{"status": "ok", "message": "Станция уже в избранном"}`.

### `DELETE /api/v1/stations/favorites/{station_id}` → `200` — USER
Удаление из избранного. `404`, если станции не было в избранном.

---

## Панель администратора

Все эндпоинты требуют роль `admin` — иначе `403`. Проверка навешена на весь роутер целиком.

### `GET /api/v1/admin/stats` → `200`
```json
{ "total_users": 3, "total_stations": 2034, "active_stations": 2033,
  "stream_availability_percentage": 99.9, "active_sessions": 2 }
```

### `POST /api/v1/admin/stations` → `201`
Создание станции вместе с её основным потоком.
```json
{ "name": "My Radio", "stream_url": "https://example.com/stream.mp3",
  "country": "France", "country_code": "FR",
  "latitude": 48.85, "longitude": 2.35, "language": "french",
  "tags": ["jazz", "chill"], "codec": "MP3", "bitrate": 128 }
```
Поле `tags` принимает **и список** (`["jazz","chill"]`), **и строку через запятую** (`"jazz,chill"`) — приводится к нормализованному списку в нижнем регистре. Обязательны только `name`, `stream_url`, `country`.

Одним запросом создаются записи в трёх таблицах: `stations`, `station_streams` и `stream_health`.

Ошибки: `400` — станция с таким `stream_url` уже существует (`stream_url` уникален).

### `PATCH /api/v1/admin/stations/{station_id}` → `200`
Частичное обновление — передавайте только изменяемые поля. Доступны все поля станции, а также `stream_url` (применяется к основному потоку в `station_streams`).

Ошибки: `404` — станция не найдена; `400` — такой `stream_url` уже занят другим потоком.

### `DELETE /api/v1/admin/stations/{station_id}` → `200`
Удаление станции. Каскадно удаляются её потоки (`station_streams`), телеметрия (`stream_health`) и записи в избранном у всех пользователей (`favorites`).

### `POST /api/v1/admin/trigger-stream-check` → `200`
Принудительный запуск проверки доступности всех потоков. Обходит все станции (до 10 параллельных запросов), обновляет `stream_health`: `is_active`, `response_time_ms`, `check_fail_count`, `last_checked_at`. Поток помечается неактивным после 2 неудачных проверок подряд.

> Операция долгая: на каталоге в ~2000 станций занимает около 6 минут. Запрос держит соединение до полного завершения.

---

## Модель токенов

| | Access-токен | Refresh-токен |
|---|---|---|
| Срок | 15 минут | 30 дней от входа, ротация не продлевает |
| Где хранится в браузере | В памяти JS (переменная), не в `localStorage` | httpOnly-cookie — JavaScript её не видит |
| Как передаётся | `Authorization: Bearer` | Браузер прикладывает сам, только к `/api/v1/auth/*` |
| Что хранит сервер | Ничего | SHA-256 хэш текущего и предыдущего токена в `user_sessions` |

**Почему так.** XSS может прочитать всё, что лежит в `localStorage`. Раньше там лежал refresh-токен на 30 дней: украв его, злоумышленник получал доступ со своей машины на месяц. Теперь refresh-токен скрипту недоступен, а access-токен после кражи работает не дольше 15 минут.

**CSRF.** Cookie уходит только на `/auth/refresh` и `/auth/logout` и с флагом `SameSite=Strict` не прикладывается к запросам с чужих сайтов. Даже если бы приложилась, новый access-токен приходит в теле ответа, а прочитать его чужой сайт не даёт CORS. Фронтенд и API работают на одном origin (прокси Vite в разработке, nginx в продакшне), поэтому cookie получается first-party.

**Мгновенный отзыв.** В access-токене есть claim `sid` — id сессии. На каждом запросе сессия проверяется поиском по первичному ключу, поэтому выход, отзыв сессии или смена пароля действуют сразу, а не через 15 минут. Токен без `sid` или с `sid` чужой сессии отклоняется.

**Ротация и обнаружение кражи.** См. [`POST /auth/refresh`](#post-apiv1authrefresh--200). Фронтенд делает ровно одно обновление на все параллельные запросы (single-flight), иначе ротация принимала бы собственные запросы вкладки за атаку. Гонку между вкладками гасит 30-секундное окно на сервере.

**Очистка.** Раз в час (`SESSION_CLEANUP_INTERVAL_SECONDS`) истёкшие и отозванные сессии удаляются, чтобы таблица не росла бесконечно.

**Требования к секретам.** `SECRET_KEY` и `SECRET_PEPPER` обязательны, не короче 32 байт (RFC 7518 для HMAC-SHA256), значений по умолчанию нет ни в коде, ни в `docker-compose.yml`. Сгенерировать: `openssl rand -hex 32`.

**IP клиента за прокси.** nginx перезаписывает `X-Forwarded-For` своим `$remote_addr`, а uvicorn доверяет этому заголовку только от частных подсетей (`FORWARDED_ALLOW_IPS` в `backend/Dockerfile`). Без этого все пользователи выглядели бы для бэкенда как IP nginx, и лимит на вход был бы общим на всех.

### Переход с предыдущей версии

Таблицы создаются через `create_all()`, а он не добавляет колонки в уже существующие таблицы. В базе, созданной до этого изменения, выполните один раз:
```sql
ALTER TABLE user_sessions ADD COLUMN previous_token_hash VARCHAR(64);
ALTER TABLE user_sessions ADD COLUMN rotated_at TIMESTAMPTZ;
CREATE INDEX ix_user_sessions_previous_token_hash ON user_sessions (previous_token_hash);
-- старые refresh-токены лежали в localStorage и могли утечь: закрываем все прежние сессии
UPDATE user_sessions SET is_revoked = true;
```
Либо пересоздайте базу: `docker compose down -v`. После обновления всем пользователям нужно войти заново.

---

## Коды ошибок

| Код | Когда возникает |
|---|---|
| `400` | Нарушение бизнес-правил: занятый email/username/URL, неверный старый пароль |
| `401` | Токен отсутствует, недействителен, истёк, не того типа; сессия отозвана или истекла; повторное использование refresh-токена; неверный логин или пароль |
| `403` | Недостаточно прав (нужна роль admin) либо учётная запись отключена |
| `404` | Запрошенный объект не найден |
| `422` | Ошибка валидации входных данных |
| `429` | Превышено ограничение частоты запросов (`/auth/login`, `/auth/register`) |

Формат ошибки валидации содержит и человекочитаемое сообщение, и машинные подробности:
```json
{ "detail": "Некорректный адрес электронной почты; Пароль должен содержать минимум 8 символов",
  "validation_errors": [ ... ] }
```
Остальные ошибки возвращаются в стандартном виде: `{ "detail": "текст ошибки" }`.
