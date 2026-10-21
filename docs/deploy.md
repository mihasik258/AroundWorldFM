# Развёртывание на VDS

Пошаговая инструкция: от чистого сервера до работающего сайта с HTTPS и Telegram-ботом. Займёт около 30 минут, большая часть — ожидание DNS и сборки.

## Как это устроено

```
Интернет ──443──▶ Caddy (сертификат, HTTPS) ──▶ nginx (сайт, защита) ──▶ FastAPI ──▶ PostgreSQL
                                                                            ▲
                                                       Telegram-бот ────────┘
```

Всё запускается одной командой через Docker Compose ([`docker-compose.prod.yml`](../docker-compose.prod.yml)). Снаружи открыты только порты 80 и 443. Сертификат Let's Encrypt Caddy получает и продлевает сам. База каждый день сохраняется в `./backups`.

## Что понадобится

| | Минимум | Лучше |
|---|---|---|
| Сервер | 1 vCPU, 1 ГБ RAM, 10 ГБ диска | 2 vCPU, 2 ГБ RAM, 20 ГБ |
| ОС | Ubuntu 22.04 / 24.04 или Debian 12 | |
| Домен | любой, например `aroundfm.ru` | |

Telegram Mini App работает только по HTTPS, поэтому домен обязателен: по голому IP сертификат не выдаётся.

## Шаг 1. Домен смотрит на сервер

В панели регистратора домена создайте DNS-записи:

| Тип | Имя | Значение |
|---|---|---|
| A | `@` | IP вашего VDS |
| A | `www` | IP вашего VDS |

Если у сервера есть IPv6 — добавьте такие же записи типа `AAAA`. Если IPv6 нет, AAAA-записей быть не должно, иначе сертификат может не выпуститься.

Проверка (с вашего компьютера, обновление DNS занимает от минут до пары часов):

```bash
dig +short aroundfm.ru
```

Должен вернуться IP сервера.

## Шаг 2. Подготовка сервера

Зайдите на сервер:

```bash
ssh root@<IP сервера>
```

Создайте пользователя, чтобы не работать под root, и перейдите в него:

```bash
adduser deploy
usermod -aG sudo deploy
su - deploy
```

Если памяти 1–2 ГБ, добавьте swap — без него сборка фронтенда может упасть:

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

Установите Docker и Make:

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker deploy
sudo apt-get install -y make git
```

Выйдите и зайдите снова (`exit`, затем `su - deploy`), чтобы заработал `docker` без `sudo`. Проверка: `docker compose version`.

Файрвол — разрешаем только SSH и веб:

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443
sudo ufw enable
```

Если у хостера есть свой файрвол в панели — откройте там те же порты: 22, 80, 443 (TCP) и 443 (UDP).

## Шаг 3. Код на сервере

Сервер берёт код из GitHub, поэтому сначала **закоммитьте и запушьте** все изменения со своего компьютера.

```bash
git clone https://github.com/mihasik258/AroundWorldFM.git
cd AroundWorldFM
```

Если репозиторий приватный, git попросит логин и токен: создайте его в GitHub → Settings → Developer settings → Personal access tokens (fine-grained, доступ на чтение к этому репозиторию).

## Шаг 4. Настройки

```bash
make env
nano .env
```

`make env` создаёт `.env` и сам генерирует все секреты: `SECRET_KEY`, `SECRET_PEPPER`, `POSTGRES_PASSWORD`, `BOT_API_SECRET`. Вам нужно вписать только:

```dotenv
DOMAIN=aroundfm.ru
ACME_EMAIL=you@example.com
```

`ACME_EMAIL` — ваша почта: Let's Encrypt пишет на неё, если с сертификатом что-то не так.

Остальное (`ENVIRONMENT`, `PUBLIC_URL`, `SEED_DEMO_USERS`) продакшен-конфиг выставляет сам и игнорирует значения из `.env`.

**Сохраните копию `.env` в надёжном месте.** Секреты нельзя менять после запуска:

| Если сменить | Что случится |
|---|---|
| `SECRET_KEY` | Все пользователи выйдут из аккаунтов |
| `SECRET_PEPPER` | Ни один пароль больше не подойдёт |
| `POSTGRES_PASSWORD` | Бэкенд не подключится к уже созданной базе |

## Шаг 5. Telegram-бот

Можно пропустить и вернуться позже — сайт работает и без бота.

1. Напишите [@BotFather](https://t.me/BotFather) → `/newbot`, придумайте имя и username (должен кончаться на `bot`). BotFather пришлёт токен.
2. Впишите в `.env`:
   ```dotenv
   TELEGRAM_BOT_TOKEN=1234567890:AA...
   TELEGRAM_BOT_USERNAME=aroundfm_bot
   ```
   Username — без `@`.
3. По желанию в BotFather: `/setdescription`, `/setabouttext`, `/setuserpic`. Команды и кнопку «Радио» бот настраивает сам при запуске.

## Шаг 6. Запуск

```bash
make prod-up
```

Первая сборка идёт 3–7 минут. Что происходит:

1. Собираются образы бэкенда, фронтенда и бота.
2. Стартует PostgreSQL.
3. Одноразовый контейнер `migrate` создаёт таблицы и загружает ~2000 станций.
4. Стартуют бэкенд, nginx, Caddy и сервис бэкапов.
5. Caddy получает сертификат (несколько секунд после старта).

Если настроили бота:

```bash
make prod-bot
```

Создайте администратора (пароль спросит, минимум 12 символов):

```bash
make prod-admin USERNAME=admin EMAIL=you@example.com
```

Демо-пользователей `admin`/`listener` с публичными паролями в продакшене нет и быть не может.

Сразу после запуска в каталоге около 2000 станций из комплекта поставки. Добрать станции со всего мира (Африка, Латинская Америка, Азия, Океания):

```bash
make prod-import ARGS="--dry-run"
make prod-import
```

Первая команда показывает, что будет добавлено, вторая добавляет и сразу проверяет потоки. Занимает около 5–10 минут. Подробности отбора — в README, раздел «Управление». Каталог обновляется только по этой команде; запускайте её, когда захотите, например раз в пару месяцев.

## Шаг 7. Проверка

```bash
docker compose -f docker-compose.prod.yml ps -a
```

Все сервисы должны быть `Up` (у `backend` и `frontend` — `healthy`), `migrate` — `Exited (0)`.

Откройте `https://aroundfm.ru` — должен быть замок в адресной строке, глобус и музыка. Затем:

- войдите администратором → иконка щита → статистика;
- в Telegram найдите бота → `/start` → «Открыть AroundFM»: сайт откроется внутри Telegram, вход выполнится сам;
- на сайте: Аккаунт → Telegram → «Подключить» → бот пришлёт «Готово» → теперь `/favorites` в боте показывает ваше избранное.

## Обновление

На своём компьютере закоммитьте и запушьте изменения, затем на сервере:

```bash
cd ~/AroundWorldFM
make prod-backup
git pull
make prod-up
make prod-bot
```

Миграции базы применяются автоматически до запуска нового бэкенда. Если миграция упала, новый бэкенд не запустится; причина — в `docker compose -f docker-compose.prod.yml logs migrate`.

## Резервные копии

Сервис `backup` раз в сутки сохраняет базу в `~/AroundWorldFM/backups/aroundfm-<дата>.dump` и удаляет копии старше 14 дней (`BACKUP_KEEP_DAYS`). Копия вручную — `make prod-backup`.

Копии лежат на том же сервере: если сервер умрёт, пропадут и они. Периодически забирайте их к себе:

```bash
scp deploy@<IP сервера>:~/AroundWorldFM/backups/*.dump ./aroundfm-backups/
```

Восстановление из копии:

```bash
docker compose -f docker-compose.prod.yml stop backend bot
docker compose -f docker-compose.prod.yml exec -T db \
  pg_restore --clean --if-exists --no-owner -U aroundfm -d aroundfm < backups/aroundfm-<дата>.dump
docker compose -f docker-compose.prod.yml start backend bot
```

Переезд на другой сервер: тот же код, **тот же `.env`** и последний `.dump` — восстановить по командам выше после `make prod-up`.

## Если что-то не работает

| Симптом | Что проверить |
|---|---|
| Сайт не открывается, ошибка сертификата | `docker compose -f docker-compose.prod.yml logs caddy`. Обычно: DNS ещё не указывает на сервер (`dig +short домен`), закрыт порт 80 или 443 в ufw или в панели хостера, лишняя AAAA-запись |
| `502 Bad Gateway` | Бэкенд не поднялся: `logs backend` и `logs migrate` |
| Сборка падает на `npm ci` с нехваткой памяти | Нет swap — шаг 2 |
| Бот молчит | `logs bot`. Неверный `TELEGRAM_BOT_TOKEN` или бот не запущен (`make prod-bot`) |
| Кнопки бота открывают браузер, а не Mini App | `DOMAIN` пуст или сайт не по HTTPS |
| «Ссылка устарела» при привязке Telegram | Ссылка живёт 10 минут; создайте новую в «Аккаунте» |
| Станции не играют | Часть потоков бывает недоступна; проверка раз в час выключает мёртвые. Вручную: админка → «Проверить потоки» |

Полезные команды:

```bash
make prod-logs
docker compose -f docker-compose.prod.yml logs backend --tail=100
docker compose -f docker-compose.prod.yml restart backend
docker compose -f docker-compose.prod.yml ps
df -h && free -h
```

По `X-Request-ID` из ответа с ошибкой (или `request_id` в теле ответа `500`) запрос находится в логах: `logs backend | grep <id>`.

## Технические детали

- Бэкенд работает в `WEB_CONCURRENCY` процессах (по умолчанию 2). Фоновые задачи — очистка сессий и проверка потоков — защищены блокировкой в PostgreSQL и выполняются в одном процессе.
- Лимиты частоты запросов: основной барьер — nginx (общий для всех процессов), дополнительно — лимиты в приложении на вход и регистрацию.
- Логи: JSON, ротация Docker — 5 файлов по 10 МБ на контейнер.
- Лимиты памяти контейнеров: БД и бэкенд по 512 МБ, остальные по 128 МБ.
- Swagger (`/docs`) в продакшене выключен.
