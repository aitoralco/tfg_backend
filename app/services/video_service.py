from sqlalchemy.orm import Session
from app.models.video_model import VideoModel
from app.schemas.video_schema import VideoCreate, VideoRead
from fastapi import UploadFile, HTTPException, status
from fastapi.responses import StreamingResponse

from pathlib import Path
import shutil
import uuid
import mimetypes
import re
import base64
from typing import List


def save_video(db: Session, video_file: UploadFile, user_id: int, video_title: str):
    """Save video metadata in DB and write file to disk with a unique filename.

    Returns the DB VideoModel instance.
    """
    # directorio app/videos relativo al paquete app
    videos_dir = Path(__file__).resolve().parents[1] / "videos"
    videos_dir.mkdir(parents=True, exist_ok=True)

    ext = Path(video_file.filename).suffix
    unique_filename = f"{uuid.uuid4().hex}{ext}"
    file_path = videos_dir / unique_filename

    # save video info to database (guardar el nombre único)
    new_video = {
        "user_id": user_id,
        "title": video_title,
        "file_name": unique_filename,
        "processed": False,
    }

    db_video = VideoModel(**new_video)
    db.add(db_video)
    db.commit()
    db.refresh(db_video)

    with file_path.open("wb") as buffer:
        shutil.copyfileobj(video_file.file, buffer)

    try:
        video_file.file.close()
    except Exception:
        pass

    return db_video


# --- funciones para streaming con soporte Range ---
def _parse_range(range_header: str | None, file_size: int) -> tuple[int, int]:
    if not range_header:
        return 0, file_size - 1
    m = re.match(r"bytes=(\d*)-(\d*)", range_header)
    if not m:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Range header")
    start_str, end_str = m.groups()
    if start_str == "" and end_str != "":
        # suffix: last N bytes (Range: bytes=-500)
        suffix = int(end_str)
        start = max(file_size - suffix, 0)
        end = file_size - 1
    else:
        start = int(start_str) if start_str != "" else 0
        end = int(end_str) if end_str != "" else file_size - 1
    if start < 0 or end >= file_size or start > end:
        raise HTTPException(status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
                            detail="Requested Range Not Satisfiable")
    return start, end


def _file_iterator(path: Path, start: int, end: int, chunk_size: int = 1024 * 1024):
    with path.open("rb") as f:
        f.seek(start)
        remaining = end - start + 1
        while remaining > 0:
            read_size = min(chunk_size, remaining)
            chunk = f.read(read_size)
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


def get_video_stream(file_name: str, range_header: str | None = None) -> StreamingResponse:
    """Return a StreamingResponse that supports HTTP Range requests for the given file_name.

    The file is looked up under app/videos/<file_name>.
    """
    videos_dir = Path(__file__).resolve().parents[1] / "videos"
    file_path = videos_dir / file_name
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video file not found")

    file_size = file_path.stat().st_size
    start, end = _parse_range(range_header, file_size)

    content_length = end - start + 1
    content_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"

    headers = {
        "Accept-Ranges": "bytes",
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Content-Length": str(content_length),
    }

    status_code = status.HTTP_206_PARTIAL_CONTENT if range_header else status.HTTP_200_OK

    return StreamingResponse(_file_iterator(file_path, start, end),
                             status_code=status_code,
                             media_type=content_type,
                             headers=headers)


def get_videos_previews(db: Session, user_id: int = None, offset: int = 0, limit: int = 10, size: int = 1024) -> List[dict]:
    """Return a list of dicts with id, title, file_name and base64 preview of the first `size` bytes.

    - offset: starting row offset
    - limit: max number of videos to return (capped by 50)
    - size: number of initial bytes to read from each file
    """
    limit = min(limit, 50)
    if user_id:
        videos = db.query(VideoModel).filter(VideoModel.user_id == user_id).order_by(VideoModel.id).offset(offset).limit(limit).all()
    else:
        videos = db.query(VideoModel).order_by(VideoModel.id).offset(offset).limit(limit).all()
        
    previews: List[dict] = []
    videos_dir = Path(__file__).resolve().parents[1] / "videos"
    for v in videos:
        record = {"id": v.id, "title": v.title, "file_name": v.file_name, "preview": None}
        if v.file_name:
            path = videos_dir / v.file_name
            if path.exists() and path.is_file():
                try:
                    with path.open("rb") as f:
                        data = f.read(size)
                        record["preview"] = base64.b64encode(data).decode("ascii")
                except Exception:
                    record["preview"] = None
        previews.append(record)
    return previews