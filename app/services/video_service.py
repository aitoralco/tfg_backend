from sqlalchemy.orm import Session
from app.models.video_model import VideoModel
from app.models.video_status_model import VideoStatusModel
from app.schemas.video_schema import VideoCreate, VideoRead
from app.filesystem import FileSystemClient
from app.cache_redis.redis_engine import RedisEngine
from app.cache_redis.tasks import process_video
from fastapi import UploadFile, HTTPException, status
from fastapi.responses import StreamingResponse

from pathlib import Path
import uuid
import mimetypes
import re
import base64
from typing import List


def create_video_status(db: Session, status_name: str):
    """
        Create a new status name for videos
    """

    new_status = {
        "status_name": status_name
    }

    db_model = VideoStatusModel(**new_status)
    db.add(db_model)
    db.commit()
    db.refresh(db_model)

    return db_model


def save_video(db: Session, video_file: UploadFile, user_id: int, video_title: str, video_description: str):
    """Save video metadata in DB and write file to disk with a unique filename.

    Returns the DB VideoModel instance.
    """

    # Generar nombre único para el video
    ext = Path(video_file.filename).suffix
    unique_filename = f"{uuid.uuid4().hex}{ext}"

    # save video info to database (guardar el nombre único)
    new_video = {
        "user_id": user_id,
        "title": video_title,
        "file_name": unique_filename,
        "status_id": 2, #2 es el default para unprocessed
        "description": video_description
    }

    db_video = VideoModel(**new_video)
    try:
        try:
            db.add(db_video)

            # Flush para enviar a DB y generar un ID
            db.flush()

            # Asignar el id a group_id
            db_video.group_id = db_video.id

        except Exception as db_err:
            db.rollback()

            raise HTTPException(
                status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"A database error ocured while saving the video metadata: {db_err}"
            )

        # Stremear el archivo directamente al minio desde memoria
        fs_client = FileSystemClient()
        try:
            fs_client.upload_video_stream(
                file_stream=video_file.file,
                filename=unique_filename,
                user_id=user_id,
                size=video_file.size,
                group_id=db_video.group_id
            )

        except Exception as minio_err:
            raise HTTPException(
                status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An error ocured while saving the video: {minio_err}"
            )

        finally:
            # Cerrar file stream
            try:
                video_file.file.close()
            except Exception:
                pass

        # Enviar tarea a redis
        try:
            redis_engine = RedisEngine()
            redis_engine.enqueue_job(
                process_video,  # función a usar 
                db_video.id     # ID del video a proceasr (después de subida a MinIO y DB)
            )
            #print(f"Successfully enqueued processing task for video ID {db_video.id}.")
        except Exception as redis_err:
            raise HTTPException(
                status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An error ocured while queueing video to process: {redis_err}"
            )

        # Commit y cerrar toda la transacción
        db.commit()
        db.refresh(db_video)
        return db_video
    
    except HTTPException:
        raise
    except Exception as unexpected_err:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected system failure occurred: {unexpected_err}"
        )


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

    

    if user_id and user_id != 0:
        print("get_videos_previews called with user_id:", user_id)
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