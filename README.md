# EduHelper API

FastAPI + PostgreSQL + SQLAlchemy Async + Alembic. REST `/api/v1`, OpenAPI `/docs`, администрирование `/admin/`.

## Запуск

Скопируйте `.env.example` в `.env`, задайте случайные POSTGRES_PASSWORD/SECRET_KEY, согласуйте пароль DATABASE_URL. Получите Argon2id хеш командой ниже. В `.env` заключайте хеш в одинарные кавычки, чтобы Docker Compose не подставлял переменные вместо символов `$`.

```powershell
python -m pip install -r requirements.txt
python -c "from argon2 import PasswordHasher; import getpass; print(PasswordHasher().hash(getpass.getpass()))"
docker compose up -d --build
docker compose exec api python -m app.import_legacy
```

IMPORT_GROUP_PASSWORD задаёт исходный пароль 4992 (12+ символов). Повторный импорт сохраняет изменения. Начальное расписание публикуется на 18 недель; далее староста повторяет нужные дни через приложение. Миграция схемы выполняется Alembic при запуске контейнера.

Публичные GET: groups, groups/{id}, groups/{id}/homework (archive/cursor), groups/{id}/calendar?start=...&end=..., subgroups. Записи ДЗ POST/PUT/DELETE. Датированный день GET/PUT days/{date}, POST days/{date}/repeat. Недельный шаблон GET/PUT templates/{weekday}, POST .../repeat. Подгруппы POST/PUT/DELETE. Повторение принимает start и weeks, заменяет указанные даты в одной транзакции. Auth: login, refresh, logout. Admin: GET/POST groups, PUT groups/{id}, POST groups/{id}/revoke под /admin.

## Production

На VPS установите Docker Compose, Nginx, certbot. Клонируйте репозиторий в `/opt/eduhelper`. `.env` держите только на сервере, права 600. PostgreSQL не публикуется наружу, API доступен только через loopback:18080. Настройка Nginx в deploy/nginx.conf. Сначала получите сертификат `certbot certonly --webroot -w /var/www/letsencrypt -d eduhelper.cosmomine.ru`, затем включите HTTPS-конфигурацию. Включите certbot.timer. Внешний адрес: https://eduhelper.cosmomine.ru.

Обновление: `git pull --ff-only && docker compose up -d --build`. Перед изменениями схемы сделайте резервную копию: `docker compose exec -T db pg_dump -U eduhelper eduhelper > backup.sql`. Восстановление: `docker compose exec -T db psql -U eduhelper eduhelper < backup.sql`. Не удаляйте volume PostgreSQL.

## Проверки

```powershell
python -m pip install pytest pytest-asyncio httpx aiosqlite
python -m pytest -q
```

Тесты по умолчанию используют изолированный SQLite Async, не рабочую БД. PostgreSQL и Alembic дополнительно проверяются на VPS. Гость читает только опубликованные активные группы. Редактор ограничен своей группой, администратор может менять любую. Смена группового пароля и отключение группы отзывают доступ немедленно. Refresh токены хешированы и ротируются. Панель хранит токены только в памяти вкладки. Login ограничен десятью попытками за минуту на IP (один процесс). Для нескольких API worker нужен общий Redis limiter.

Telegram-уведомления и FCM не включены. Они могут использовать API/сервисный слой в будущем без изменения клиентской авторизации. Анализ исходника: docs/MIGRATION.md.

Проверки на PostgreSQL: задайте TEST_DATABASE_URL, указывающий **только на отдельную тестовую БД**. Тестовая фикстура очищает таблицы этой БД. Подробный отчёт: docs/VERIFICATION.md. Web-клиент обслуживается Nginx из /var/www/eduhelper; backend по-прежнему независимо обслуживает /api/v1 и /admin/.
