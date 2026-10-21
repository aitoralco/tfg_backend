# Backend

[English](README.md) | **Español**

API REST del proyecto, construida con **FastAPI**. Usa **PostgreSQL** (datos), **Redis** (cola de trabajos para el worker) y **MinIO** (almacenamiento de vídeos, compatible con S3).

## Tecnología

- **FastAPI** + **Uvicorn**
- **SQLAlchemy** (ORM) + **Alembic** (migraciones de BD)
- **uv** (gestión de dependencias, `pyproject.toml` + `uv.lock`)
- **Docker / Docker Compose** (el stack completo está en `../tfg_dockercompose`)

## Estructura del proyecto

```
app/
├── main.py          # app FastAPI
├── core/            # configuración (config.py), auth, seguridad
├── db/
│   ├── session.py   # engine, SessionLocal, Base
│   └── starter.py   # seed idempotente de datos base
├── models/          # modelos SQLAlchemy (fuente del esquema de la BD)
├── routes/ schemas/ services/
├── cache_redis/ filesystem/ utils/
alembic/
├── env.py           # toma la URL de la BD de settings.DATABASE_URL
└── versions/        # ficheros de migración (versionados en git)
alembic.ini
```

## Variables de entorno

La configuración la carga `app/core/config.py` desde variables de entorno o desde un fichero `.env` en la raíz del proyecto (ver `.env.example`).

| Grupo | Variables |
|---|---|
| Postgres | `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_SERVER`, `POSTGRES_PORT`, `POSTGRES_DB` |
| Redis | `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`, `REDIS_PASSWORD` |
| MinIO | `FILESYSTEM_URL`, `FILESYSTEM_PUBLIC_URL`, `FILESYSTEM_ID_KEY`, `FILESYSTEM_ACCESS_KEY`, `FORCE_PATH_STYLE`, `REGION_NAME`, `BUCKET_NAME` |
| Auth | `JWT_SECRET_KEY` |
| Admin por defecto (seed) | `ADMIN_USERNAME` (por defecto `admin`), `ADMIN_EMAIL` (por defecto `admin@admin.com`), `ADMIN_PASSWORD` |
| Otras | `DEBUG` (por defecto `false`, imprime las consultas SQL) |

Todas son obligatorias incluso para comandos que solo tocan la BD (Alembic, seed), porque `Settings()` lo valida todo al importarse.

## Ejecución con Docker Compose (stack completo)

Desde `../tfg_dockercompose`:

```bash
docker compose up --build -d
```

Orden de arranque:

```
db-postgres (healthy) ──► backend-migrate ──(exit 0)──► backend-fastapi
                                                    └─► worker-rq
```

`backend-migrate` usa la misma imagen que el backend, ejecuta

```bash
uv run alembic upgrade head && uv run python -m app.db.starter
```

y termina. El backend y el worker solo arrancan si ha terminado correctamente, así que la API nunca se ejecuta contra un esquema inexistente o desactualizado. Se ejecuta en cada `up`: con la BD vacía lo crea todo, con la BD al día no hace nada.

Comprobaciones útiles:

```bash
docker compose ps -a                     # backend-migrate debe estar "Exited (0)"
docker compose logs backend-migrate      # migraciones aplicadas y salida del seed
```

## Ejecución en local (desarrollo)

1. Levanta solo los servicios de datos desde `../tfg_dockercompose`:
   ```bash
   docker compose up -d db-postgres cache-redis filesystem-minio
   ```
2. Crea `.env` a partir de `.env.example`, apuntando los hosts a `localhost` y usando las mismas credenciales que el `.env` del compose (`DB_USER` → `POSTGRES_USER`, etc.).
3. Instala las dependencias:
   ```bash
   uv sync
   ```
4. Prepara la BD (esquema + datos base):
   ```bash
   uv run alembic upgrade head
   uv run python -m app.db.starter
   ```
5. Arranca la API en modo desarrollo (recarga automática):
   ```bash
   uv run uvicorn app.main:app --reload --port 8000
   ```
   La API queda disponible en http://127.0.0.1:8000 (documentación en `/docs`).

## Base de datos

### Esquema: Alembic

El esquema se define **solo** con los modelos de `app/models/` y se aplica **solo** mediante migraciones de Alembic. No uses `Base.metadata.create_all`: las tablas creadas así no quedan registradas en `alembic_version` y las migraciones posteriores fallarán.

Flujo para cambiar el esquema:

1. Modifica el/los modelo(s) en `app/models/`.
2. Con la BD local al día, genera la migración:
   ```bash
   uv run alembic revision --autogenerate -m "descripcion corta"
   ```
3. Revisa el fichero generado en `alembic/versions/`. El autogenerate no lo detecta todo (p. ej. un renombrado de columna lo ve como drop + add, y algunos cambios de tipo se le escapan).
4. Aplícala y pruébala en local:
   ```bash
   uv run alembic upgrade head
   ```
5. Haz commit del fichero de migración. El siguiente `docker compose up --build` la aplica automáticamente.

Nunca edites una migración que ya se haya aplicado en otro entorno; crea una nueva.

Otros comandos útiles:

```bash
uv run alembic current           # revisión aplicada en la BD
uv run alembic history           # lista de migraciones
uv run alembic downgrade -1      # deshace la última migración
uv run alembic stamp head        # marca como al día una BD existente (creada sin Alembic)
```

### Datos base: seed

`app/db/starter.py` inserta los datos que el backend necesita para funcionar, solo si todavía no existen (se puede ejecutar las veces que haga falta):

- Roles: `admin`, `user`, `test`
- Estados de vídeo: `error`, `unprocessed`, `processing_0`, `processing_dw`, `processing_ew`, `processing_dem`, `processed`
- Usuario admin por defecto, a partir de `ADMIN_USERNAME` / `ADMIN_EMAIL` / `ADMIN_PASSWORD`

```bash
uv run python -m app.db.starter
```

### Inspeccionar la BD

```bash
docker compose exec db-postgres psql -U <DB_USER> -d <DB_NAME>
```

## Documentación

- `docs/endpoints.md`: lista de endpoints y su estado
- `docs/frontend_api_guide.md`: guía de uso de la API para el frontend
- `tests/api_tests/*.http`: colecciones de peticiones para probar la API

## Licencia

© 2026 Aitor Alonso Coloma. Con licencia [MIT](LICENSE).
