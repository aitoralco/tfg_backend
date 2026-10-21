# Whaler Backend — Endpoint Audit

Base URL: `http://127.0.0.1:8000`

Auth: JWT Bearer token. Obtain via `POST /users/login`.

---

## USERS `/users`

| Method | Path | Auth | Description | Status |
|--------|------|------|-------------|--------|
| POST | `/users/register` | — | Create a new user (role=user by default) | ✅ Working |
| POST | `/users/login` | — | Authenticate; returns JWT access token + user info | ✅ Working |
| GET | `/users/me` | User | Get own profile | ✅ Working |
| PATCH | `/users/me` | User | Update own data — requires `current_password`; use `new_password` to change it | ✅ Working |
| DELETE | `/users/me` | User | Delete own account — requires `current_password` in body | ✅ Working |
| GET | `/users/all` | Admin | List all users | ✅ Working |
| GET | `/users/{user_id}` | User | Get any user's profile | ✅ Working |
| PUT | `/users/{user_id}` | Admin | Update any user (username, email, password, role_id) | ✅ Working |
| DELETE | `/users/{user_id}` | Admin | Delete any user | ✅ Working |
| POST | `/users/roles` | Admin | Create a new role | ✅ Working |

### Request bodies

**POST /users/register**
```json
{ "username": "str", "email": "email", "password": "str" }
```

**POST /users/login** → returns `{ "access_token", "token_type", "user" }`
```json
{ "username": "str", "password": "str" }
```

**PATCH /users/me**
```json
{
  "current_password": "required",
  "username": "optional",
  "email": "optional",
  "new_password": "optional"
}
```

**DELETE /users/me**
```json
{ "current_password": "required" }
```

**PUT /users/{user_id}** (admin)
```json
{
  "username": "optional",
  "email": "optional",
  "password": "optional",
  "role_id": "optional"
}
```

Role IDs (from the seed): `1` = admin, `2` = user, `3` = test.

---

## VIDEOS `/videos`

| Method | Path | Auth | Description | Status |
|--------|------|------|-------------|--------|
| GET | `/videos/previews` | — | Paginated list of shared videos with JPEG thumbnail | ✅ Working |
| GET | `/videos/search` | — | Search shared videos by title/description/uploader/date | ✅ Working |
| GET | `/videos/mine` | User | Paginated list of own videos (including private), with filters and sorting | ✅ Working |
| GET | `/videos/{video_id}` | Optional* | Stream the original video with HTTP Range support | ✅ Working |
| GET | `/videos/{video_id}/info` | Optional* | Video metadata + processing results summary (DW, EW, DEM, classification) | ✅ Working |
| GET | `/videos/{video_id}/dw/stream` | Optional* | Stream the DW annotated video (detections drawn) with HTTP Range support | ✅ Working |
| GET | `/videos/{video_id}/ew/crops` | Optional* | Paginated presigned URLs of the EW whale crops | ✅ Working |
| GET | `/videos/{video_id}/dem/crops` | Optional* | Paginated presigned URLs of the DEM crops | ✅ Working |

\* Shared videos are public. Private videos (`shared: false`) are only served to their owner or an admin; anyone else gets `404`. The token can be sent in the `Authorization` header or, for `<video src>` (which cannot send headers), as `?token=<jwt>`. An invalid or expired token is treated as anonymous.
| POST | `/videos/upload` | User | Upload video to MinIO, generate thumbnail and enqueue processing (multipart/form-data) | ✅ Working |
| PATCH | `/videos/{video_id}` | User (owner) | Update title, description, or shared flag | ✅ Working |
| DELETE | `/videos/{video_id}` | User (owner) | Delete video from DB and all its files from MinIO | ✅ Working |
| GET | `/videos/meta/{video_id}` | — | Debug: return video_id if record exists | ✅ Working (debug) |
| POST | `/videos/create_status` | User | Debug: create a new video status entry | ✅ Working (debug) |
| PUT | `/videos/enqueue_test` | — | Debug: enqueue a test Redis job | ✅ Working (debug) |

### Query parameters

**GET /videos/previews**
- `user_id` (int, optional) — filter by uploader
- `offset` (int, default 0) — pagination offset
- `limit` (int, default 10, max 50) — page size
- `size` (int, default 1024) — legacy parameter, currently ignored

Response: `{ "previews": [...], "total": int, "offset": int, "limit": int }`. Sorted by id.

**GET /videos/search**
- `q` (str, optional) — search title and description (case-insensitive substring)
- `uploader` (str, optional) — filter by username (case-insensitive substring)
- `date_from` (ISO 8601, optional) — earliest upload date
- `date_to` (ISO 8601, optional) — latest upload date
- `offset`, `limit` (same as previews)

Same response as previews, sorted by newest first, with `preview: null`.

**GET /videos/mine**
- `q` (str, optional) — search title and description
- `date_from`, `date_to` (ISO 8601, optional)
- `status_id` (int, optional) — filter by processing status
- `sort_by` (`created_at` | `updated_at` | `title`, default `created_at`)
- `order` (`asc` | `desc`, default `desc`)
- `offset`, `limit` (same as previews)

Same response as previews.

**GET /videos/{video_id}/ew/crops** and **GET /videos/{video_id}/dem/crops**
- `offset` (int, default 0)
- `limit` (int, default 20, max 50)

Response: `{ "crops": [{ "key", "url" }], "total": int, "offset": int, "limit": int }`. Sorted by key.

**GET /videos/{video_id}**, **GET /videos/{video_id}/dw/stream**
Support `Range: bytes=start-end` header for progressive download, and `token` (optional JWT) to play private videos.

### Upload form fields

**POST /videos/upload**
- `video_name` (str)
- `description` (str)
- `file` (binary)

**PATCH /videos/{video_id}**
```json
{ "title": "optional", "description": "optional", "shared": "optional bool" }
```

---

## Notes

- **Thumbnails**: on upload, the backend extracts the first frame with ffmpeg and stores it as a JPEG in MinIO.
  `previews`/`mine` return it base64-encoded in `preview`, and `info` in `thumbnail`. If ffmpeg failed, the value is `null`.

- **Processing**: on upload, the backend enqueues `process_video(video_id)` in Redis (RQ). The worker (`../tfg_worker`) runs the
  DW → EW → DEM → CW phases and uploads the results to MinIO under `{user_id}/{group_id}/{video_id}/`. `GET /videos/{id}/info`
  reports which phases have results; the `dw/stream`, `ew/crops` and `dem/crops` endpoints serve them.

- **Video status** is updated by the worker. IDs (from the seed): `1` error, `2` unprocessed (default on upload),
  `3` processing_0, `4` processing_dw, `5` processing_ew, `6` processing_dem, `7` processed.

- **Presigned URLs** (crops) are valid for 1 hour and are generated with `FILESYSTEM_PUBLIC_URL`, so they can be opened from the browser.

- **Streaming** uses HTTP Range requests — the frontend should use a standard `<video src="/videos/{id}">` element;
  browsers will issue Range requests automatically. For private videos, append `?token=<jwt>`.

- **Previews** (`previews`, `search`, `mine`) include the `shared` flag of each video.

- All authenticated endpoints require `Authorization: Bearer <token>` header.
