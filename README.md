# Backend

**English** | [Español](README.es.md)

REST API of the project, built with **FastAPI**. It uses **PostgreSQL** (data), **Redis** (job queue for the worker) and **MinIO** (video storage, S3 compatible).

## Technology

- **FastAPI** + **Uvicorn**
- **SQLAlchemy** (ORM) + **Alembic** (DB migrations)
- **uv** (dependency management, `pyproject.toml` + `uv.lock`)
- **Docker / Docker Compose** (the full stack lives in `../tfg_dockercompose`)

## Project structure

```
app/
├── main.py          # FastAPI app
├── core/            # settings (config.py), auth, security
├── db/
│   ├── session.py   # engine, SessionLocal, Base
│   └── starter.py   # idempotent seed of base data
├── models/          # SQLAlchemy models (source of the DB schema)
├── routes/ schemas/ services/
├── cache_redis/ filesystem/ utils/
alembic/
├── env.py           # takes the DB URL from settings.DATABASE_URL
└── versions/        # migration files (versioned in git)
alembic.ini
```

## Environment variables

Settings are loaded by `app/core/config.py` from environment variables or from a `.env` file in the project root (see `.env.example`).

| Group | Variables |
|---|---|
| Postgres | `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_SERVER`, `POSTGRES_PORT`, `POSTGRES_DB` |
| Redis | `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`, `REDIS_PASSWORD` |
| MinIO | `FILESYSTEM_URL`, `FILESYSTEM_PUBLIC_URL`, `FILESYSTEM_ID_KEY`, `FILESYSTEM_ACCESS_KEY`, `FORCE_PATH_STYLE`, `REGION_NAME`, `BUCKET_NAME` |
| Auth | `JWT_SECRET_KEY` |
| Default admin (seed) | `ADMIN_USERNAME` (default `admin`), `ADMIN_EMAIL` (default `admin@admin.com`), `ADMIN_PASSWORD` |
| Other | `DEBUG` (default `false`, prints SQL queries) |

All of them are required even for commands that only touch the DB (Alembic, seed), because `Settings()` validates everything on import.

## Running with Docker Compose (full stack)

From `../tfg_dockercompose`:

```bash
docker compose up --build -d
```

Startup order:

```
db-postgres (healthy) ──► backend-migrate ──(exit 0)──► backend-fastapi
                                                    └─► worker-rq
```

`backend-migrate` uses the same image as the backend, runs

```bash
uv run alembic upgrade head && uv run python -m app.db.starter
```

and exits. The backend and the worker only start if it finished successfully, so the API never runs against a missing or outdated schema. It runs on every `up`: on an empty DB it creates everything, on an up-to-date DB it does nothing.

Useful checks:

```bash
docker compose ps -a                     # backend-migrate must be "Exited (0)"
docker compose logs backend-migrate      # applied migrations and seed output
```

## Running locally (development)

1. Start only the data services from `../tfg_dockercompose`:
   ```bash
   docker compose up -d db-postgres cache-redis filesystem-minio
   ```
2. Create `.env` from `.env.example`, pointing hosts to `localhost` and using the same credentials as the compose `.env` (`DB_USER` → `POSTGRES_USER`, etc.).
3. Install dependencies:
   ```bash
   uv sync
   ```
4. Prepare the DB (schema + base data):
   ```bash
   uv run alembic upgrade head
   uv run python -m app.db.starter
   ```
5. Start the API in development mode (auto reload):
   ```bash
   uv run uvicorn app.main:app --reload --port 8000
   ```
   The API is available at http://127.0.0.1:8000 (docs at `/docs`).

## Database

### Schema: Alembic

The schema is defined **only** by the models in `app/models/` and applied **only** through Alembic migrations. Do not use `Base.metadata.create_all`: tables created that way are not registered in `alembic_version` and later migrations will fail.

Workflow to change the schema:

1. Modify the model(s) in `app/models/`.
2. With the local DB up to date, generate the migration:
   ```bash
   uv run alembic revision --autogenerate -m "short description"
   ```
3. Review the generated file in `alembic/versions/`. Autogenerate does not detect everything (e.g. column renames are seen as drop + add, some type changes are missed).
4. Apply and test it locally:
   ```bash
   uv run alembic upgrade head
   ```
5. Commit the migration file. The next `docker compose up --build` applies it automatically.

Never edit a migration that has already been applied in another environment; create a new one instead.

Other useful commands:

```bash
uv run alembic current           # revision applied to the DB
uv run alembic history           # list of migrations
uv run alembic downgrade -1      # undo the last migration
uv run alembic stamp head        # mark an existing DB (created without Alembic) as up to date
```

### Base data: seed

`app/db/starter.py` inserts the data the backend needs to work, only if it does not exist yet (safe to run any number of times):

- Roles: `admin`, `user`, `test`
- Video statuses: `error`, `unprocessed`, `processing_0`, `processing_dw`, `processing_ew`, `processing_dem`, `processed`
- Default admin user, from `ADMIN_USERNAME` / `ADMIN_EMAIL` / `ADMIN_PASSWORD`

```bash
uv run python -m app.db.starter
```

### Inspecting the DB

```bash
docker compose exec db-postgres psql -U <DB_USER> -d <DB_NAME>
```

## Documentation

- `docs/endpoints.md`: list of endpoints and their status
- `docs/frontend_api_guide.md`: API usage guide for the frontend
- `tests/api_tests/*.http`: request collections to test the API
