# Whaler API — Frontend Integration Guide (Angular)

Backend base URL: `http://127.0.0.1:8000`

---

## Auth

The API uses **JWT Bearer tokens**. After login, store the token (e.g. in `localStorage` or a service) and attach it to every protected request via the `Authorization` header:

```
Authorization: Bearer <access_token>
```

In Angular, the cleanest approach is an `HttpInterceptor` that adds this header automatically to every outgoing request.

The token expires after **24 hours**. When a protected endpoint returns `401`, redirect the user to login.

### Private videos

Videos with `shared: false` are private. The endpoints that work on a single video (`/videos/{id}`, `/info`, `/dw/stream`, `/ew/crops`, `/dem/crops`) only serve them to their owner or an admin; anyone else gets `404`, as if the video did not exist.

HttpClient requests already carry the token (interceptor). A `<video src>` cannot send headers, so for the two stream URLs add the token as a query parameter:

```
/videos/{id}?token=<access_token>
/videos/{id}/dw/stream?token=<access_token>
```

An invalid or expired token is ignored (treated as anonymous), so public videos keep working.

---

## Endpoints

### 1. Register

```
POST /users/register
```

**Body (JSON):**
```json
{
  "username": "string",
  "email": "user@example.com",
  "password": "string"
}
```

**Response 201:**
```json
{
  "id": 1,
  "username": "string",
  "email": "user@example.com",
  "role": { "id": 2, "name": "user" },
  "created_at": "2026-01-01T00:00:00",
  "updated_at": "2026-01-01T00:00:00"
}
```

All new users are assigned the `user` role automatically.

---

### 2. Login

```
POST /users/login
```

**Body (JSON):**
```json
{
  "username": "string",
  "password": "string"
}
```

**Response 200:**
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "username": "string",
    "email": "user@example.com",
    "role": { "id": 2, "name": "user" },
    "created_at": "...",
    "updated_at": "..."
  }
}
```

Save `access_token` and `user` in your auth service. Use `user.role.name` to know if the logged-in user is `"admin"` or `"user"`.

**Errors:** `401` invalid credentials.

---

### 3. Get own profile

```
GET /users/me
Authorization: Bearer <token>
```

**Response 200:** same `UserRead` object as in login.

Use this on app startup to restore the session if a token is already stored.

---

### 4. Update own profile

```
PATCH /users/me
Authorization: Bearer <token>
```

**Body (JSON) — all fields optional except `current_password`:**
```json
{
  "current_password": "required — current password to confirm identity",
  "username": "new username (optional)",
  "email": "new@email.com (optional)",
  "new_password": "new password (optional)"
}
```

**Response 200:** updated `UserRead`.

**Errors:** `403` if `current_password` is wrong, `401` if not logged in.

---

### 5. Delete own account

```
DELETE /users/me
Authorization: Bearer <token>
```

**Body (JSON):**
```json
{
  "current_password": "required"
}
```

**Response 204** (no body). After this, discard the token and redirect to home/login.

**Errors:** `403` if password is wrong.

---

### 6. Get any user by ID

```
GET /users/{user_id}
Authorization: Bearer <token>
```

**Response 200:** `UserRead` object.

**Errors:** `404` user not found.

---

### 7. (Admin) List all users

```
GET /users/all
Authorization: Bearer <admin token>
```

**Response 200:** array of `UserRead`.

**Errors:** `403` if the logged-in user is not admin.

---

### 8. (Admin) Update any user

```
PUT /users/{user_id}
Authorization: Bearer <admin token>
```

**Body (JSON) — all optional:**
```json
{
  "username": "string",
  "email": "string",
  "password": "string",
  "role_id": 1
}
```

Role IDs: `1` = admin, `2` = user, `3` = test.

**Response 200:** updated `UserRead`.

---

### 9. (Admin) Delete any user

```
DELETE /users/{user_id}
Authorization: Bearer <admin token>
```

**Response 204.**

---

### 10. Video home page — paginated previews

```
GET /videos/previews
```

No auth required. Anyone can call this. Only videos with `shared: true` are returned, sorted by id.

**Query params:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `offset` | int | 0 | Pagination offset |
| `limit` | int | 10 | Page size (max 50) |
| `user_id` | int | — | Filter by uploader ID (optional) |
| `size` | int | 1024 | Legacy parameter, currently ignored |

**Response 200:**
```json
{
  "previews": [
    {
      "id": 1,
      "title": "Video title",
      "description": "...",
      "file_name": "abc123.MP4",
      "uploader": "username",
      "created_at": "2026-01-01T00:00:00",
      "status": { "id": 7, "status_name": "processed" },
      "shared": true,
      "preview": "<base64 string or null>"
    }
  ],
  "total": 38,
  "offset": 0,
  "limit": 10
}
```

`preview` is a base64-encoded **JPEG thumbnail** (first frame extracted by ffmpeg). Display it with an `<img>` element:

```html
<img [src]="'data:image/jpeg;base64,' + item.preview" alt="preview" />
```

If `preview` is `null`, no thumbnail could be generated at upload time — show a placeholder image instead.

Use `total` + `offset` + `limit` to build pagination controls.

---

### 11. Search videos

```
GET /videos/search
```

No auth required.

**Query params:**
| Param | Type | Description |
|-------|------|-------------|
| `q` | string | Searches title and description (case-insensitive) |
| `uploader` | string | Filter by uploader username (case-insensitive) |
| `date_from` | ISO 8601 | Earliest upload date, e.g. `2026-01-01` |
| `date_to` | ISO 8601 | Latest upload date, e.g. `2026-12-31` |
| `offset` | int | Pagination offset (default 0) |
| `limit` | int | Page size (default 10, max 50) |

All params are optional — omitting all of them returns all shared videos sorted by newest first. Only videos with `shared: true` are returned.

**Response 200:** same shape as `/videos/previews` but `preview` is always `null` (search is lightweight, no thumbnails fetched).

---

### 11b. My videos

```
GET /videos/mine
Authorization: Bearer <token>
```

All videos of the logged-in user, **including private ones** (`shared: false`).

**Query params (all optional):**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `q` | string | — | Searches title and description (case-insensitive) |
| `date_from` | ISO 8601 | — | Earliest upload date |
| `date_to` | ISO 8601 | — | Latest upload date |
| `status_id` | int | — | Filter by processing status (see [Video status values](#video-status-values)) |
| `sort_by` | string | `created_at` | `created_at`, `updated_at` or `title` |
| `order` | string | `desc` | `asc` or `desc` |
| `offset` | int | 0 | Pagination offset |
| `limit` | int | 10 | Page size (max 50) |

**Response 200:** same shape as `/videos/previews`, with the JPEG thumbnail in `preview`.

**Errors:** `401` if not logged in, `400` if a date is not valid ISO 8601.

---

### 12. Watch a video (streaming)

```
GET /videos/{video_id}
```

No auth required for shared videos. Private videos need the owner's or an admin's token (see [Private videos](#private-videos)).

Just use this URL as the `src` of a standard HTML5 `<video>` element. The browser will send `Range` requests automatically and the backend will serve the video progressively (like YouTube):

```html
<video controls [src]="apiBase + '/videos/' + videoId"></video>
```

For a private video, use `apiBase + '/videos/' + videoId + '?token=' + token`.

Or in Angular using `HttpClient` with `responseType: 'blob'` if you need more control (e.g. custom progress bar).

**Response:** `200 OK` or `206 Partial Content` with `Content-Type: video/mp4` and proper `Content-Range` headers.

**Errors:** `404` if the video doesn't exist.

---

### 12b. Video detail and processing results

```
GET /videos/{video_id}/info
```

No auth required for shared videos. Private videos need the owner's or an admin's token (see [Private videos](#private-videos)). Returns the video metadata plus a summary of what the worker has produced so far. Use it to build the video detail page and decide which result sections to show.

**Response 200:**
```json
{
  "id": 42,
  "title": "Video title",
  "description": "...",
  "uploader": "username",
  "created_at": "2026-01-01T00:00:00",
  "status": { "id": 7, "status_name": "processed" },
  "shared": true,
  "thumbnail": "<base64 JPEG or null>",
  "dw":  { "available": true, "video_key": "1/42/42/dw/abc_annotated.mp4", "label_count": 310 },
  "ew":  { "available": true, "crop_count": 120 },
  "dem": { "available": true, "txt_count": 120, "crop_count": 95 },
  "classification": {
    "total_images": 95,
    "classified_images": 95,
    "errors": 0,
    "classes": {
      "species_name": { "count": 80, "percentage": 84.2, "avg_confidence": 0.91 }
    }
  }
}
```

- `dw.available`: the annotated video exists → it can be played with `/videos/{id}/dw/stream`.
- `ew.available` / `dem.available`: crops exist → list them with `/videos/{id}/ew/crops` / `/videos/{id}/dem/crops`.
- `classification` is `null` until the last phase finishes.

**Errors:** `404` if the video doesn't exist.

---

### 12c. Watch the annotated video (DW)

```
GET /videos/{video_id}/dw/stream
```

No auth required for shared videos. Private videos need the owner's or an admin's token (see [Private videos](#private-videos)). Same as [Watch a video](#12-watch-a-video-streaming), but serves the video with the detected whales drawn on it. Supports `Range` requests.

```html
<video controls [src]="apiBase + '/videos/' + videoId + '/dw/stream'"></video>
```

**Errors:** `404` if the video doesn't exist or the DW phase hasn't produced the video yet.

---

### 12d. Whale crops (EW) and mark crops (DEM)

```
GET /videos/{video_id}/ew/crops
GET /videos/{video_id}/dem/crops
```

No auth required for shared videos. Private videos need the owner's or an admin's token (see [Private videos](#private-videos)). Paginated list of the crop images produced by the worker.

**Query params:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `offset` | int | 0 | Pagination offset |
| `limit` | int | 20 | Page size (max 50) |

**Response 200:**
```json
{
  "crops": [
    { "key": "1/42/42/ew/abc/crop_0001.jpg", "url": "http://localhost:9000/videos-bucket/...&X-Amz-Signature=..." }
  ],
  "total": 120,
  "offset": 0,
  "limit": 20
}
```

`url` is a **presigned MinIO URL valid for 1 hour**: use it directly as the `src` of an `<img>`. If the page stays open longer, request the page again to get fresh URLs.

**Errors:** `404` if the video doesn't exist. If the phase has no results yet, the response is `200` with an empty `crops` list.

---

### 13. Upload a video

```
POST /videos/upload
Authorization: Bearer <token>
Content-Type: multipart/form-data
```

**Form fields:**
| Field | Type | Description |
|-------|------|-------------|
| `video_name` | string | Title of the video |
| `description` | string | Description |
| `file` | File | The video file |

In Angular:
```typescript
const form = new FormData();
form.append('video_name', title);
form.append('description', description);
form.append('file', fileInput.files[0]);

this.http.post('/videos/upload', form).subscribe(...);
```

Do **not** set `Content-Type` manually — Angular sets it automatically with the correct boundary when using `FormData`.

**Response 201:**
```json
{
  "message": "Video uploaded successfully",
  "video_id": 42
}
```

After the upload the backend generates the thumbnail and enqueues the video for processing. Its status starts as `unprocessed` and the worker updates it (see [Video status values](#video-status-values)).

**Errors:**
- `401` — not logged in.
- `500` — failed to save to storage or queue for processing. The body will contain `{"detail": "Error saving video to storage: ..."}` or `{"detail": "Error queueing video for processing: ..."}`. Show this message to the user so they can retry.

In Angular:
```typescript
this.http.post('/videos/upload', form).subscribe({
  next: (res) => { /* success */ },
  error: (err) => {
    const msg = err.error?.detail ?? 'Unknown upload error';
    // show msg to user
  }
});
```

---

### 14. Update a video

```
PATCH /videos/{video_id}
Authorization: Bearer <token>
```

Only the owner of the video can update it.

**Body (JSON) — all optional:**
```json
{
  "title": "New title",
  "description": "New description",
  "shared": true
}
```

**Response 200:** full `VideoRead` object:
```json
{
  "id": 42,
  "user_id": 1,
  "title": "New title",
  "file_name": "abc123.MP4",
  "description": "New description",
  "shared": true,
  "status": { "id": 2, "status_name": "unprocessed" },
  "created_at": "...",
  "updated_at": "..."
}
```

**Errors:** `403` if not the owner, `404` if video not found.

---

### 15. Delete a video

```
DELETE /videos/{video_id}
Authorization: Bearer <token>
```

Only the owner can delete. Removes the record from the database and all its files from storage (original video, thumbnail and processing results).

**Response 204** (no body).

**Errors:** `403` if not the owner, `404` if video not found.

---

## Angular quick-start patterns

### Auth interceptor

Functional interceptor (Angular 15+), registered with `provideHttpClient(withInterceptors([authInterceptor]))`:

```typescript
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const token = localStorage.getItem('token');
  const authService = inject(AuthService);
  const router = inject(Router);

  const authReq = token
    ? req.clone({ setHeaders: { Authorization: `Bearer ${token}` } })
    : req;

  return next(authReq).pipe(
    catchError((err: HttpErrorResponse) => {
      if (err.status === 401) {
        authService.clearSession();
        router.navigate(['/login']);
      }
      return throwError(() => err);
    })
  );
};
```

### Pagination helper

```typescript
interface PagedResponse {
  previews: VideoPreview[];
  total: number;
  offset: number;
  limit: number;
}

loadPage(page: number, limit = 10) {
  const offset = page * limit;
  return this.http.get<PagedResponse>(`/videos/previews?offset=${offset}&limit=${limit}`);
}
```

### Video player component

```html
<!-- Angular template -->
<video
  controls
  preload="metadata"
  [src]="videoUrl"
  type="video/mp4">
</video>
```

```typescript
get videoUrl() {
  return `http://127.0.0.1:8000/videos/${this.videoId}`;
}
```

The browser handles Range requests automatically — no extra code needed.

---

## Error codes reference

| Code | Meaning |
|------|---------|
| 200 | OK |
| 201 | Created (register, upload) |
| 204 | Deleted (no body) |
| 206 | Partial Content (video range) |
| 400 | Bad request (invalid params) |
| 401 | Not authenticated / token expired |
| 403 | Forbidden (wrong password or not owner/admin) |
| 404 | Resource not found |
| 422 | Validation error (missing or wrong-type fields) |
| 500 | Server error — body has `{"detail": "..."}` with the reason |

---

## Video status values

The `status.status_name` field on a video can be:

| id | status_name | Meaning |
|----|-------------|---------|
| 1 | `error` | Processing failed |
| 2 | `unprocessed` | Just uploaded, worker hasn't started |
| 3 | `processing_0` | Worker started (downloading the video) |
| 4 | `processing_dw` | Detecting whales |
| 5 | `processing_ew` | Extracting whales |
| 6 | `processing_dem` | Detecting marks and classifying species |
| 7 | `processed` | Done |

You can use this to show a progress indicator on the video card.
