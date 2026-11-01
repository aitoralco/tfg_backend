# Diario de desarrollo

## 2026-10-29 - Estado de los tests

Comando: `uv run pytest --cov --cov-report=term`

Resultado: **201 passed, 9 xfailed, 0 failed, 4 warnings** (unos 15 s).

### Bugs conocidos (xfail)

Los 9 xfail corresponden a 4 bugs que siguen sin arreglar:

| Bug | Tests | Fichero |
|---|---|---|
| Borrar un usuario con vídeos da 500: la relación `UserModel.videos` no tiene `cascade` y se intenta poner `videos.user_id = NULL` | 1 | `tests/integration/test_users_api.py::TestDeleteMe` |
| La paginación no se valida (`offset=-1`, `limit=-1`, `limit=0`) en `/videos/previews` y `/videos/search` | 6 | `tests/integration/test_videos_listing.py` |
| Si falla Redis después de subir el vídeo, se hace rollback en la BD pero el fichero se queda huérfano en MinIO | 1 | `tests/integration/test_videos_upload.py` |
| `Range: bytes=0-5000` sobre un fichero más pequeño devuelve 416 en vez de recortar el final (RFC 9110, 14.1.2) | 1 | `tests/unit/test_parse_range.py` |

Ojo: `xfail_strict = true` está activado en `pyproject.toml`. Cuando se arregle uno de estos bugs, su test pasará a XPASS y la suite fallará hasta quitar el `@pytest.mark.xfail`.

Los dos xfail que he quitado en los cambios de hoy (username duplicado en el registro y en `PATCH /users/me`) ya pasan, así que el arreglo funciona.

### Warnings

Los 4 warnings vienen del typo `min_lenght` en `app/schemas/user_schema.py` (2 campos en `UserSelfUpdate` y 2 en `UserAdminUpdate`). Pydantic no reconoce el parámetro y lo ignora, por lo que **la longitud mínima de la contraseña no se está aplicando**. Ningún test lo detecta porque no hay ninguno que pruebe una contraseña corta.

Además, `min_length` en un `EmailStr` no aporta nada: `EmailStr` ya valida el formato.

### Cobertura: 93 % (868 sentencias, 58 sin cubrir)

| Módulo | Cobertura | Qué falta |
|---|---|---|
| `app/services/user_service.py` | 92 % | Línea 105: 409 por email duplicado en `PATCH /users/me` (solo hay test para username). Líneas 52-55 y 116-119: los `except IntegrityError`, que no se alcanzan porque la comprobación previa los evita; habría que simular la condición de carrera con `monkeypatch`. |
| `app/routes/video_route.py` | 79 % | Endpoints de debug sin tests: `POST /videos/create_status`, `GET /videos/meta/{id}`, `PUT /videos/enqueue_test`. |
| `app/services/video_service.py` | 95 % | `create_video_status` (42-46); ffmpeg lanzando una excepción (116-117), solo está probado el código de retorno distinto de 0; rama de error inesperado en `save_video` (135-137). |
| `app/filesystem/filesystem_client.py` | 87 % | `upload_video` (legacy), no se usa en ningún sitio. |
| `app/utils/response_model.py` | 0 % | No se usa. Código muerto. |
| `app/cache_redis/tasks.py` | 50 % | `process_video` es un stub vacío. |

### Huecos que la cobertura no muestra

- No hay test de que `PUT /users/{id}` (admin) con un username o email ya usado devuelva 409. Ahora mismo da 500.
- No hay tests de longitud mínima de username ni de contraseña.
- No hay tests de permisos para los endpoints de debug. Ahora mismo cualquier usuario logueado puede usar `create_status`, y `enqueue_test` y `meta` no piden autenticación.

### Pendiente

- [ ] Corregir `min_lenght` -> `min_length` y aplicar las mismas reglas en `UserCreate`.
- [ ] Comprobar duplicados también en `admin_update_user`.
- [ ] Arreglar los 4 bugs de los xfail y quitar los marcadores.
- [ ] Proteger (o eliminar) los endpoints de debug y añadir sus tests.
- [ ] Añadir los tests que faltan de la lista anterior.

## 2026-10-29 (noche) - Borrar usuario con vídeos (en curso, sin commit)

Modo de trabajo: lo implemento yo; Claude solo revisa, explica y da pistas, sin editar código.

### Hecho

- `app/models/user_model.py`: `videos = relationship(..., cascade="all")`. El borrado en la BD ya funciona: al borrar el usuario se borran sus vídeos. Antes daba 500 porque SQLAlchemy intentaba poner `videos.user_id = NULL` y la columna es `nullable=False`.

### En curso: borrar los ficheros del usuario en MinIO

Estado actual de `delete_db_user` (`app/services/user_service.py`): el usuario se borra pero **su directorio de MinIO se queda**, sin errores en los logs.

Causa: los vídeos se consultan **después** de `db.commit()`, cuando el cascade ya los ha borrado. La lista sale vacía y no se borra nada.

Arreglo elegido (opción B): borrar todo el prefijo `{user_id}/` en MinIO **después** del commit en la BD, sin depender de los `group_id`.
- S3/MinIO no permite borrar por prefijo: primero hay que listar las claves (paginator `list_objects_v2`) y luego pasarlas a `delete_objects`, como hace `delete_group`.
- El prefijo tiene que acabar en `/` (`"5/"`). Con `"5"` también se borrarían los ficheros de los usuarios 50, 51...
- Hay que envolver la llamada a MinIO en `try/except`, como en `delete_video`, para que un fallo de almacenamiento no dé 500 cuando el usuario ya está borrado.
- Opción A (descartada): sacar los `group_ids` de `user.videos` **antes** del `db.delete(user)`.

### Por deshacer o revisar

- He cambiado la firma de `delete_group` a `group_ids: List[int]` (y su llamada en `video_service.delete_video`). Esto rompe `tests/unit/test_filesystem_client.py:101`. Con la opción B, lo suyo es volver a dejarla como estaba (o refactorizar a un método genérico `delete_prefix(prefix)`).
- Si ya no se usan, quitar el import de `VideoModel` en `user_service.py` y `from typing import List` en `filesystem_client.py`.

### Para darlo por cerrado

- [ ] Quitar el `@pytest.mark.xfail` de `tests/integration/test_users_api.py:224` (con `xfail_strict` daría XPASS).
- [ ] `uv run pytest`, la suite entera.
- [ ] Opcional: un test que compruebe que en el bucket no queda ningún objeto con el prefijo del usuario.
- [ ] Prueba manual: crear usuario, subir vídeo, `DELETE /users/me`. Comprobar la BD (`docker exec -it <contenedor> psql -U <usuario> -d cetaceans -c "SELECT ..."`) y MinIO.

### Otros problemas detectados en la revisión (no estaban en la lista de pendientes)

- [ ] La subida guarda el vídeo en un fichero temporal (`tempfile` en `save_video`) para ffmpeg. El requisito es subirlo en stream sin guardar nada en el backend.
- [ ] Con `date_to=YYYY-MM-DD` se interpreta como 00:00 y se pierden los vídeos de ese día (`/search` y `/mine`).
- [ ] `PUT /users/{id}` con un `role_id` que no existe y `POST /users/roles` con un rol duplicado dan 500. Además, `RoleCreate` obliga a mandar el id.
- [ ] Cambio de contraseña: sin longitud mínima, sin confirmación, y los JWT antiguos siguen siendo válidos 24 h.
- [ ] Un admin puede borrarse a sí mismo o borrar al último admin.
- [ ] Detalles menores: `Content-Range` en respuestas 200; `size` sin usar y `if user_id:` en `/previews`; `sort_by`/`order` inválidos ignorados en silencio; `/search` sin miniaturas; código muerto (`utils/response_model.py`, `core/exceptions.py`, `upload_video` antiguo).
