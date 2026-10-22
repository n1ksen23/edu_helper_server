# EduHelper API

FastAPI, PostgreSQL, SQLAlchemy Async, Alembic. REST `/api/v1`, OpenAPI `/docs`. Администрирование — в приложении: Настройки → «Заявки и группы». Отдельная веб-панель удалена.

## Правила данных

Расписание хранится только для конкретных дат в `days`. Шаблонов и повторяющихся правил нет. Повторение дня создаёт независимые копии на выбранные недели: изменение одной даты не меняет остальные. Тип недели — информация календаря, он не фильтрует пары и не изменяет сохранённый день.

Подгруппы — только фиксированные метки `Пг 1` и `Пг 2` (`subgroup_id=1/2`, `null` — вся группа). Справочника и API управления подгруппами нет. Совпадающие номера пар допускаются для параллельных занятий. В ДЗ разделение описывается обычным текстом. Ученик не выбирает подгруппу.

Заявка на новую группу: публичный POST `/group-requests` с `group_number` и `contacts`. Контакты доступны только администратору: GET `/admin/group-requests`, PATCH `/admin/group-requests/{id}` со статусом pending/approved/rejected. POST /admin/group-requests/{id}/accept с GroupIn создаёт группу и принимает новую заявку одной транзакцией. Повторное принятие возвращает 409. Управление доступно в Flutter: Настройки → «Заявки и группы». Заявка сама не создаёт и не публикует группу. Администратор создаёт группу и передаёт пароль по оставленным контактам. Ограничение: пять заявок в час на IP, без публичного чтения контактов.

## Запуск

Скопируйте `.env.example` в `.env`, задайте случайные POSTGRES_PASSWORD/SECRET_KEY и согласуйте пароль DATABASE_URL. Хеш Argon2id заключайте в одинарные кавычки, чтобы Compose не подставлял переменные вместо `$`.

```powershell
python -m pip install -r requirements.txt
python -c "from argon2 import PasswordHasher; import getpass; print(PasswordHasher().hash(getpass.getpass()))"
docker compose up -d --build
docker compose exec api python -m app.import_legacy
```

IMPORT_GROUP_PASSWORD задаёт исходный пароль 4992 (12+ символов). Импорт идемпотентен и не перезаписывает изменения. Исходное чередование недель разрешается при импорте в конкретные даты на первые 18 недель; дальше редактор задаёт или копирует нужные дни. JSON используется только для импорта.

Публичные GET: groups, groups/{id}, groups/{id}/homework (archive/cursor), groups/{id}/calendar?start=...&end=.... ДЗ: POST/PUT/DELETE homework. День: GET/PUT days/{date}, POST days/{date}/repeat и weeks/{monday}/repeat (start, weeks — число повторов, interval_weeks=1|2, overwrite). Повторение создаёт независимые даты в одной транзакции; overwrite=false пропускает сохранённые дни, true заменяет их. Копируются только сохранённые исходные дни Пн–Сб. GET subgroups оставлен только как статический список двух меток для совместимости ранее установленных клиентов. Auth: login, refresh, logout. Admin: GET/POST groups, PUT groups/{id}, POST groups/{id}/revoke под /admin.

## Production

Git checkout: `/opt/eduhelper`. `.env` только на сервере, права 600. PostgreSQL не публикуется наружу; API слушает loopback:18080. Nginx: deploy/nginx.conf. API и Android используют HTTPS https://eduhelper.cosmomine.ru. Web обслуживается из `/var/www/eduhelper`.

Обновление: `git pull --ff-only && docker compose up -d --build`. Alembic выполняется при запуске. Перед миграциями сделайте резервную копию: `docker compose exec -T db pg_dump -U eduhelper eduhelper > backup.sql`. Восстановление: `docker compose exec -T db psql -U eduhelper eduhelper < backup.sql`. Не удаляйте volume PostgreSQL.

Миграция 0003 удаляет прежние таблицы шаблонов и подгрупп, сохраняя фактически отображавшиеся пары каждой даты. Откат этой миграции требует восстановления резервной копии. До production-обновления создана копия `/opt/eduhelper-backups/before-0003-2026-10-22.sql.gz`; сравнение до/после подтвердило совпадение расписания на 126 датах.

## Проверки

```powershell
python -m pip install pytest pytest-asyncio httpx aiosqlite
python -m pytest -q
```

По умолчанию тесты используют SQLite. Для PostgreSQL задайте TEST_DATABASE_URL, указывающий только на отдельную тестовую БД: фикстура очищает её таблицы. Проверяются права, отзыв сессий, архив, даты, копирование, параллельные пары двух подгрупп, импорт и заявки. Рабочая база при тестировании не затрагивается.

Пароли — Argon2id. Access JWT на 10 минут, отзыв проверяется на каждом запросе. Refresh-токены хешируются и ротируются. Панель хранит токены в памяти. Login ограничен десятью попытками в минуту на IP; для нескольких API worker нужен общий limiter (Redis). Контакты заявок не включаются в публичные ответы или URL. Telegram/FCM не реализованы.

Тип недели рассчитывается автоматически от недели, содержащей 1 сентября соответствующего учебного года: первая — верхняя, затем недели чередуются по понедельникам. В январе отсчёт продолжается; новый цикл начинается в неделю с 1 сентября. Ручных настроек начальной даты и типа недели нет. Сохранённые пары не изменяются.
