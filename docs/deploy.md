# Развёртывание на сервере

Как поднять AroundFM на VDS с HTTPS. Каждая команда ниже выполнена на чистой Ubuntu 24.04; после каждого шага есть проверка.

Схема продакшена: Caddy (HTTPS) → nginx (статика, лимиты) → FastAPI → PostgreSQL, рядом бот и сервис бэкапов. Всё описано в [`docker-compose.prod.yml`](../docker-compose.prod.yml). Наружу открыты только 80 и 443.

## Что нужно заранее

- VDS: Ubuntu 22.04/24.04 или Debian 12, от 1 ГБ RAM и 10 ГБ диска.
- Домен. Без домена HTTPS не будет, а без HTTPS не работает Telegram Mini App.
- Все изменения закоммичены и запушены в GitHub: сервер берёт код оттуда.

Дальше `example.com` — ваш домен, `1.2.3.4` — IP сервера.

## 1. DNS

У регистратора домена создайте две записи:

| Тип | Имя | Значение |
|---|---|---|
| A | `@` | `1.2.3.4` |
| A | `www` | `1.2.3.4` |

Если у сервера нет IPv6, записей `AAAA` быть не должно: Let's Encrypt пойдёт по IPv6 и не выдаст сертификат.

Проверка (на своём компьютере; DNS обновляется от минут до пары часов):

```bash
nslookup example.com
nslookup www.example.com
```

Оба должны вернуть `1.2.3.4`. Пока не вернули, шаг 6 не начинайте.

## 2. Сервер

```bash
ssh root@1.2.3.4
```

Пользователь для работы (спросит пароль, его же потом спросит `sudo`):

```bash
adduser deploy
usermod -aG sudo deploy
su - deploy
```

Swap нужен, если памяти 2 ГБ или меньше: без него сборка фронтенда падает. Сначала посмотрите, нет ли его уже:

```bash
swapon --show
```

Если вывод пустой:

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

Docker, make, git, файрвол:

```bash
sudo apt-get update
sudo apt-get install -y make git ufw
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker deploy
```

Чтобы группа `docker` применилась, перелогиньтесь: `exit`, затем `su - deploy`.

```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443
sudo ufw enable
```

Правило для 22 обязательно идёт **до** `ufw enable`, иначе SSH отвалится. Если у хостера есть файрвол в панели, откройте там 22/tcp, 80/tcp, 443/tcp и 443/udp.

Проверка:

```bash
docker compose version
sudo ufw status
```

Первая команда печатает версию без `sudo`, вторая показывает `Status: active` и порты 22, 80, 443.

## 3. Код

```bash
git clone https://github.com/mihasik258/AroundWorldFM.git
cd AroundWorldFM
```

Для приватного репозитория git спросит логин и токен: GitHub → Settings → Developer settings → Personal access tokens, fine-grained, доступ Contents: Read к этому репозиторию.

## 4. `.env`

```bash
make env
nano .env
```

`make env` создаёт `.env` и генерирует секреты. Если `.env` уже есть, команда ничего не делает. Впишите две строки:

```dotenv
DOMAIN=example.com
ACME_EMAIL=you@example.com
```

`DOMAIN` — без `https://` и без `www`. На `ACME_EMAIL` Let's Encrypt пишет, если сертификат не продлевается. Остальные строки не трогайте: `ENVIRONMENT`, `PUBLIC_URL` и `SEED_DEMO_USERS` продакшен выставляет сам.

Скопируйте `.env` к себе (`scp deploy@1.2.3.4:~/AroundWorldFM/.env .`) и не меняйте секреты после запуска:

- сменили `SECRET_KEY` — всех выкинет из аккаунтов;
- сменили `SECRET_PEPPER` — не подойдёт ни один пароль;
- сменили `POSTGRES_PASSWORD` — бэкенд не подключится к уже созданной базе.

## 5. Telegram-бот (можно позже)

1. [@BotFather](https://t.me/BotFather) → `/newbot`, username должен кончаться на `bot`. BotFather пришлёт токен.
2. В `.env`:
   ```dotenv
   TELEGRAM_BOT_TOKEN=1234567890:AA...
   TELEGRAM_BOT_USERNAME=aroundfm_bot
   ```
   Username без `@`. Команды и кнопку меню бот настроит сам при старте.

## 6. Запуск

```bash
make prod-up
```

Первая сборка — 3–7 минут. Порядок: сборка образов → PostgreSQL → контейнер `migrate` (таблицы и ~2000 станций) → бэкенд, nginx, Caddy, бэкапы. Сертификат Caddy получает в первые секунды после старта.

Проверка:

```bash
docker compose -f docker-compose.prod.yml ps -a
```

| Сервис | Должно быть |
|---|---|
| `backend`, `frontend`, `db` | `Up … (healthy)` |
| `caddy`, `backup` | `Up` |
| `migrate` | `Exited (0)` |

`healthy` появляется через 20–30 секунд после старта, до этого — `health: starting`.

Откройте `https://example.com`: замок в адресной строке, глобус, играет музыка.

## 7. Администратор

```bash
make prod-admin USERNAME=admin EMAIL=you@example.com
```

Спросит пароль (не меньше 12 символов, при вводе не отображается). Ответ: `Admin admin created`. Демо-пользователей в продакшене нет.

Проверка: войдите на сайте под `admin`, в шапке появится щит, в нём — статистика.

## 8. Бот

Если заполнили шаг 5:

```bash
make prod-bot
docker compose -f docker-compose.prod.yml logs bot --tail=20
```

`make prod-bot` завершается успешно, даже если токен неверный: бот падает уже после старта и перезапускается по кругу. Поэтому смотрите логи: в них не должно быть `ValidationError` и `Unauthorized`.

Проверка: в Telegram найдите бота → `/start` → «Открыть AroundFM». Сайт откроется внутри Telegram и войдёт сам. Привязка к аккаунту: на сайте «Аккаунт» → Telegram → «Подключить», бот ответит «Готово», после этого `/favorites` в боте показывает ваше избранное.

## 9. Больше станций (по желанию)

После запуска в каталоге ~2000 станций. Добрать станции со всего мира из Radio Browser:

```bash
make prod-import ARGS="--dry-run"
make prod-import
```

Первая команда только показывает, что будет добавлено. Вторая добавляет и сразу проверяет потоки, 5–10 минут. Можно по континентам: `ARGS="--continents AF,SA"`. Сам каталог не обновляется: запускайте, когда захотите.

## 10. Первый бэкап

```bash
make prod-backup
ls -lh backups/
```

Сервис `backup` делает копию при старте и потом раз в сутки, но первая копия снимается до того, как `migrate` заполнит базу, и получается пустой (около 1 КБ). Поэтому после первого запуска сделайте копию руками: файл `manual-<дата>.dump` должен весить сотни килобайт.

## Обновление

На своём компьютере — commit и push. На сервере:

```bash
cd ~/AroundWorldFM
make prod-backup
git pull
make prod-up
make prod-bot      # только если бот настроен
```

Миграции применяются до старта нового бэкенда. Если миграция упала, новый бэкенд не стартует; причина — в `docker compose -f docker-compose.prod.yml logs migrate`.

## Бэкапы и восстановление

Автоматические копии: `backups/aroundfm-<дата>.dump`, хранятся 14 дней (`BACKUP_KEEP_DAYS` в `.env`). Ручные `manual-*.dump` не удаляются. Копии лежат на том же сервере, поэтому периодически забирайте их к себе:

```bash
scp 'deploy@1.2.3.4:~/AroundWorldFM/backups/*.dump' ./aroundfm-backups/
```

Восстановление (база заменяется содержимым копии целиком):

```bash
cd ~/AroundWorldFM
docker compose -f docker-compose.prod.yml stop backend bot
docker compose -f docker-compose.prod.yml exec -T db \
  pg_restore --clean --if-exists --no-owner -U aroundfm -d aroundfm < backups/<файл>.dump
docker compose -f docker-compose.prod.yml start backend bot
```

Переезд на другой сервер: шаги 1–3, **старый `.env`** вместо шага 4, `make prod-up`, затем восстановление из последней копии.

## Если не работает

| Симптом | Причина и что делать |
|---|---|
| Ошибка сертификата, сайт не открывается | `docker compose -f docker-compose.prod.yml logs caddy`. Обычно DNS ещё не обновился (шаг 1), закрыт 80 или 443 в ufw или в панели хостера, или есть лишняя `AAAA`-запись |
| В логах Caddy ошибки про `www.` | Нет A-записи для `www`. Основной домен при этом работает |
| `502 Bad Gateway` | Бэкенд не поднялся: `logs backend` и `logs migrate` |
| `migrate` в статусе `Exited (1)` | `logs migrate`. Если `password authentication failed` — в `.env` сменили `POSTGRES_PASSWORD` после первого запуска; верните старый |
| Сборка падает на `npm ci` | Не хватает памяти: нет swap, шаг 2 |
| Бот молчит | `logs bot`: неверный `TELEGRAM_BOT_TOKEN` или не запущен `make prod-bot` |
| Кнопка бота открывает браузер, а не Mini App | Сайт не по HTTPS или пустой `DOMAIN` |
| «Ссылка устарела» при привязке Telegram | Ссылка живёт 10 минут, создайте новую в «Аккаунте» |
| Часть станций не играет | Потоки иногда падают; фоновая проверка выключает мёртвые. Вручную: админка → «Проверить потоки» |

Полезное:

```bash
make prod-logs                                                   # все логи в реальном времени
docker compose -f docker-compose.prod.yml logs backend --tail=100
docker compose -f docker-compose.prod.yml restart backend
df -h && free -h
```

Ответ с ошибкой содержит `X-Request-ID` (у `500` — ещё и `request_id` в теле); по нему запрос находится в логах: `docker compose -f docker-compose.prod.yml logs backend | grep <id>`.

Swagger (`/docs`) в продакшене выключен намеренно.
