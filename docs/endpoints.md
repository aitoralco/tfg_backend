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

---

## VIDEOS `/videos`

| Method | Path | Auth | Description | Status |
|--------|------|------|-------------|--------|
| GET | `/videos/previews` | — | Paginated video list with first-frame bytes preview | ✅ Working |
| GET | `/videos/search` | — | Search by title/description/uploader/date | ✅ Working |
| GET | `/videos/{video_id}` | — | Stream video with HTTP Range support (progressive playback) | ✅ Working |
| POST | `/videos/upload` | User | Upload video directly to MinIO (multipart/form-data) | ✅ Working |
| PATCH | `/videos/{video_id}` | User (owner) | Update title, description, or shared flag | ✅ Working |
| DELETE | `/videos/{video_id}` | User (owner) | Delete video from DB and MinIO | ✅ Working |
| GET | `/videos/meta/{video_id}` | — | Debug: return video_id if record exists | ✅ Working (debug) |
| POST | `/videos/create_status` | User | Create a new video status entry | ✅ Working (debug) |
| PUT | `/videos/enqueue_test` | — | Debug: enqueue a test Redis job | ✅ Working (debug) |

### Query parameters

**GET /videos/previews**
- `user_id` (int, optional) — filter by uploader
- `offset` (int, default 0) — pagination offset
- `limit` (int, default 10, max 50) — page size
- `size` (int, default 1024) — bytes to fetch per video for preview

Response: `{ "previews": [...], "total": int, "offset": int, "limit": int }`

**GET /videos/search**
- `q` (str, optional) — search title and description (case-insensitive substring)
- `uploader` (str, optional) — filter by username (case-insensitive substring)
- `date_from` (ISO 8601, optional) — earliest upload date
- `date_to` (ISO 8601, optional) — latest upload date
- `offset`, `limit` (same as previews)

**GET /videos/{video_id}**  
Supports `Range: bytes=start-end` header for progressive download.

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

- **Preview bytes** come from the first `size` bytes of the raw video file in MinIO.
  These are sufficient for browsers to extract the first frame via the `<video>` element.
  Videos uploaded before MinIO integration (DB records without matching MinIO objects) return `preview: null`.

- **Video status** is managed by the background worker (Redis/RQ).
  The default status on upload is `unprocessed` (id=2).
  The worker pipeline (`process_video`) is not yet implemented.

- **Streaming** uses HTTP Range requests — the frontend should use a standard `<video src="/videos/{id}">` element;
  browsers will issue Range requests automatically.

- All authenticated endpoints require `Authorization: Bearer <token>` header.
