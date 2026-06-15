from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from app.models.video_model import VideoModel
from app.models.video_status_model import VideoStatusModel
from app.models.user_model import UserModel
from app.schemas.video_schema import VideoCreate, VideoUpdate
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
import os
import shutil
import subprocess
import tempfile
from datetime import datetime
from typing import List, Optional


def create_video_status(db: Session, status_name: str):
    db_model = VideoStatusModel(status_name=status_name)
    db.add(db_model)
    db.commit()
    db.refresh(db_model)
    return db_model


def save_video(
    db: Session,
    video_file: UploadFile,
    user_id: int,
    video_title: str,
    video_description: str,
) -> VideoModel:
    ext = Path(video_file.filename).suffix
    unique_filename = f"{uuid.uuid4().hex}{ext}"

    db_video = VideoModel(
        user_id=user_id,
        title=video_title,
        file_name=unique_filename,
        status_id=2,  # unprocessed
        description=video_description,
    )

    tmp_video_path = None
    tmp_thumb_path = None

    try:
        db.add(db_video)
        db.flush()
        db_video.group_id = db_video.id

        # Spill uploaded file to disk so ffmpeg can read it
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp_video_path = tmp.name
            shutil.copyfileobj(video_file.file, tmp)

        fs_client = FileSystemClient()

        try:
            with open(tmp_video_path, "rb") as f:
                fs_client.upload_video_stream(
                    file_stream=f,
                    filename=unique_filename,
                    user_id=user_id,
                    group_id=db_video.group_id,
                )
        except Exception as minio_err:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error saving video to storage: {minio_err}",
            )

        # Generate JPEG thumbnail — non-fatal if ffmpeg is unavailable
        try:
            tmp_thumb_path = tmp_video_path + "_thumb.jpg"
            result = subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-i", tmp_video_path,
                    "-frames:v", "1",
                    "-q:v", "2",
                    tmp_thumb_path,
                ],
                capture_output=True,
                timeout=30,
            )
            if result.returncode == 0 and os.path.exists(tmp_thumb_path):
                with open(tmp_thumb_path, "rb") as f:
                    fs_client.upload_thumbnail(f.read(), user_id, db_video.group_id)
            else:
                print(f"[thumbnail] ffmpeg returned {result.returncode}")
                print(f"[thumbnail] stderr: {result.stderr.decode(errors='replace')}")
        except Exception as thumb_err:
            print(f"[thumbnail] exception: {thumb_err}")

        try:
            redis_engine = RedisEngine()
            redis_engine.enqueue_job(process_video, db_video.id)
        except Exception as redis_err:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error queueing video for processing: {redis_err}",
            )

        db.commit()
        db.refresh(db_video)
        return db_video

    except HTTPException:
        db.rollback()
        raise
    except Exception as err:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {err}",
        )
    finally:
        try:
            video_file.file.close()
        except Exception:
            pass
        if tmp_video_path and os.path.exists(tmp_video_path):
            os.unlink(tmp_video_path)
        if tmp_thumb_path and os.path.exists(tmp_thumb_path):
            os.unlink(tmp_thumb_path)


def update_video(db: Session, video_id: int, update: VideoUpdate, user_id: int) -> VideoModel:
    video = db.query(VideoModel).filter(VideoModel.id == video_id).first()
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    if video.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your video")

    if update.title is not None:
        video.title = update.title
    if update.description is not None:
        video.description = update.description
    if update.shared is not None:
        video.shared = update.shared

    db.commit()
    db.refresh(video)
    return video


def delete_video(db: Session, video_id: int, user_id: int):
    video = db.query(VideoModel).filter(VideoModel.id == video_id).first()
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    if video.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your video")

    try:
        fs_client = FileSystemClient()
        fs_client.delete_group(video.user_id, video.group_id)
    except Exception:
        pass  # log but don't block DB deletion

    db.delete(video)
    db.commit()


# --- Video streaming (from MinIO) ---

def _parse_range(range_header: str | None, file_size: int) -> tuple[int, int]:
    if not range_header:
        return 0, file_size - 1
    m = re.match(r"bytes=(\d*)-(\d*)", range_header)
    if not m:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Range header"
        )
    start_str, end_str = m.groups()
    if start_str == "" and end_str != "":
        suffix = int(end_str)
        start = max(file_size - suffix, 0)
        end = file_size - 1
    else:
        start = int(start_str) if start_str else 0
        end = int(end_str) if end_str else file_size - 1
    if start < 0 or end >= file_size or start > end:
        raise HTTPException(
            status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
            detail="Requested Range Not Satisfiable",
        )
    return start, end


def get_video_stream(video: VideoModel, range_header: str | None = None) -> StreamingResponse:
    if not video.file_name:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Video file not available"
        )

    fs_client = FileSystemClient()
    try:
        file_size = fs_client.get_object_size(video.user_id, video.group_id, video.file_name)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Video not found in storage"
        )

    start, end = _parse_range(range_header, file_size)
    content_length = end - start + 1
    content_type = mimetypes.guess_type(video.file_name)[0] or "video/mp4"

    headers = {
        "Accept-Ranges": "bytes",
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Content-Length": str(content_length),
    }
    http_status = status.HTTP_206_PARTIAL_CONTENT if range_header else status.HTTP_200_OK

    return StreamingResponse(
        fs_client.get_object_range(video.user_id, video.group_id, video.file_name, start, end),
        status_code=http_status,
        media_type=content_type,
        headers=headers,
    )


# --- Previews & search ---

def get_videos_previews(
    db: Session,
    user_id: Optional[int] = None,
    offset: int = 0,
    limit: int = 10,
    size: int = 1024,
) -> dict:
    limit = min(limit, 50)

    query = db.query(VideoModel).filter(VideoModel.shared == True)
    if user_id:
        query = query.filter(VideoModel.user_id == user_id)

    total = query.count()
    videos = query.order_by(VideoModel.id).offset(offset).limit(limit).all()

    fs_client = FileSystemClient()
    previews: List[dict] = []
    for v in videos:
        record = {
            "id": v.id,
            "title": v.title,
            "description": v.description,
            "file_name": v.file_name,
            "uploader": v.user.username if v.user else None,
            "created_at": v.created_at,
            "status": {"id": v.status.id, "status_name": v.status.status_name},
            "preview": None,
        }
        thumbnail = fs_client.get_thumbnail(v.user_id, v.group_id)
        if thumbnail:
            record["preview"] = base64.b64encode(thumbnail).decode("ascii")
        previews.append(record)

    return {"previews": previews, "total": total, "offset": offset, "limit": limit}


def get_video_info(db: Session, video_id: int) -> dict:
    video = db.query(VideoModel).filter(VideoModel.id == video_id).first()
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")

    fs = FileSystemClient()

    thumbnail_bytes = fs.get_thumbnail(video.user_id, video.group_id)
    thumbnail = base64.b64encode(thumbnail_bytes).decode("ascii") if thumbnail_bytes else None

    dw_prefix = f"{video.user_id}/{video.group_id}/{video_id}/dw/"
    dw_objects = fs.list_objects_with_prefix(dw_prefix)
    dw_video = next(
        (o for o in dw_objects if "/labels/" not in o["key"] and not o["key"].endswith(".txt")),
        None,
    )
    dw_labels = [o for o in dw_objects if o["key"].endswith(".txt")]

    ew_prefix = f"{video.user_id}/{video.group_id}/{video_id}/ew/"
    ew_objects = fs.list_objects_with_prefix(ew_prefix)
    ew_crops = [o for o in ew_objects if o["key"].lower().endswith((".jpg", ".png"))]

    dem_prefix = f"{video.user_id}/{video.group_id}/{video_id}/dem/"
    dem_objects = fs.list_objects_with_prefix(dem_prefix)
    dem_txts = [o for o in dem_objects if o["key"].endswith(".txt")]
    dem_crops = [o for o in dem_objects if o["key"].lower().endswith((".jpg", ".png"))]

    classification = None
    classification_key = f"{video.user_id}/{video.group_id}/{video_id}/classification.json"
    raw_json = fs.get_object_bytes(classification_key)
    if raw_json:
        import json
        try:
            classification = json.loads(raw_json)
        except Exception:
            pass

    return {
        "id": video.id,
        "title": video.title,
        "description": video.description,
        "uploader": video.user.username if video.user else None,
        "created_at": video.created_at,
        "status": {"id": video.status.id, "status_name": video.status.status_name},
        "shared": video.shared,
        "thumbnail": thumbnail,
        "dw": {
            "available": dw_video is not None,
            "video_key": dw_video["key"] if dw_video else None,
            "label_count": len(dw_labels),
        },
        "ew": {
            "available": len(ew_crops) > 0,
            "crop_count": len(ew_crops),
        },
        "dem": {
            "available": len(dem_objects) > 0,
            "txt_count": len(dem_txts),
            "crop_count": len(dem_crops),
        },
        "classification": classification,
    }


def get_my_videos(
    db: Session,
    user_id: int,
    offset: int = 0,
    limit: int = 10,
    q: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    status_id: Optional[int] = None,
    sort_by: str = "created_at",
    order: str = "desc",
) -> dict:
    limit = min(limit, 50)

    query = db.query(VideoModel).filter(VideoModel.user_id == user_id)

    if q:
        pattern = f"%{q}%"
        query = query.filter(
            or_(VideoModel.title.ilike(pattern), VideoModel.description.ilike(pattern))
        )
    if status_id is not None:
        query = query.filter(VideoModel.status_id == status_id)
    if date_from:
        try:
            query = query.filter(VideoModel.created_at >= datetime.fromisoformat(date_from))
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid date_from, use ISO 8601 (YYYY-MM-DD)")
    if date_to:
        try:
            query = query.filter(VideoModel.created_at <= datetime.fromisoformat(date_to))
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid date_to, use ISO 8601 (YYYY-MM-DD)")

    sort_column = {
        "created_at": VideoModel.created_at,
        "updated_at": VideoModel.updated_at,
        "title": VideoModel.title,
    }.get(sort_by, VideoModel.created_at)
    query = query.order_by(sort_column.asc() if order == "asc" else sort_column.desc())

    total = query.count()
    videos = query.offset(offset).limit(limit).all()

    fs_client = FileSystemClient()
    previews = []
    for v in videos:
        record = {
            "id": v.id,
            "title": v.title,
            "description": v.description,
            "file_name": v.file_name,
            "uploader": v.user.username if v.user else None,
            "created_at": v.created_at,
            "status": {"id": v.status.id, "status_name": v.status.status_name},
            "preview": None,
        }
        thumbnail = fs_client.get_thumbnail(v.user_id, v.group_id)
        if thumbnail:
            record["preview"] = base64.b64encode(thumbnail).decode("ascii")
        previews.append(record)

    return {"previews": previews, "total": total, "offset": offset, "limit": limit}


def get_dw_stream(db: Session, video_id: int, range_header: str | None) -> StreamingResponse:
    video = db.query(VideoModel).filter(VideoModel.id == video_id).first()
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")

    fs = FileSystemClient()
    dw_prefix = f"{video.user_id}/{video.group_id}/{video_id}/dw/"
    dw_objects = fs.list_objects_with_prefix(dw_prefix)
    dw_video = next(
        (o for o in dw_objects if "/labels/" not in o["key"] and not o["key"].endswith(".txt")),
        None,
    )
    if not dw_video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="DW video not available yet")

    key = dw_video["key"]
    file_size = dw_video["size"]

    start, end = _parse_range(range_header, file_size)
    content_length = end - start + 1
    content_type = mimetypes.guess_type(key)[0] or "video/x-msvideo"

    headers = {
        "Accept-Ranges": "bytes",
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Content-Length": str(content_length),
    }
    http_status_code = status.HTTP_206_PARTIAL_CONTENT if range_header else status.HTTP_200_OK

    return StreamingResponse(
        fs.get_object_range_by_key(key, start, end),
        status_code=http_status_code,
        media_type=content_type,
        headers=headers,
    )


def _get_crops_page(objects: list[dict], fs: FileSystemClient, offset: int, limit: int) -> dict:
    total = len(objects)
    page = sorted(objects, key=lambda o: o["key"])[offset: offset + limit]
    crops = [{"key": o["key"], "url": fs.generate_presigned_url(o["key"])} for o in page]
    return {"crops": crops, "total": total, "offset": offset, "limit": limit}


def get_ew_crops(db: Session, video_id: int, offset: int, limit: int) -> dict:
    limit = min(limit, 50)
    video = db.query(VideoModel).filter(VideoModel.id == video_id).first()
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")

    fs = FileSystemClient()
    ew_prefix = f"{video.user_id}/{video.group_id}/{video_id}/ew/"
    crops = [
        o for o in fs.list_objects_with_prefix(ew_prefix)
        if o["key"].lower().endswith((".jpg", ".png"))
    ]
    return _get_crops_page(crops, fs, offset, limit)


def get_dem_crops(db: Session, video_id: int, offset: int, limit: int) -> dict:
    limit = min(limit, 50)
    video = db.query(VideoModel).filter(VideoModel.id == video_id).first()
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")

    fs = FileSystemClient()
    dem_prefix = f"{video.user_id}/{video.group_id}/{video_id}/dem/"
    crops = [
        o for o in fs.list_objects_with_prefix(dem_prefix)
        if o["key"].lower().endswith((".jpg", ".png"))
    ]
    return _get_crops_page(crops, fs, offset, limit)


def search_videos(
    db: Session,
    q: Optional[str] = None,
    uploader: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    offset: int = 0,
    limit: int = 10,
) -> dict:
    limit = min(limit, 50)

    query = db.query(VideoModel).join(UserModel, VideoModel.user_id == UserModel.id).filter(VideoModel.shared == True)

    if q:
        pattern = f"%{q}%"
        query = query.filter(
            or_(
                VideoModel.title.ilike(pattern),
                VideoModel.description.ilike(pattern),
            )
        )

    if uploader:
        query = query.filter(UserModel.username.ilike(f"%{uploader}%"))

    if date_from:
        try:
            query = query.filter(VideoModel.created_at >= datetime.fromisoformat(date_from))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date_from format, use ISO 8601 (YYYY-MM-DD)",
            )

    if date_to:
        try:
            query = query.filter(VideoModel.created_at <= datetime.fromisoformat(date_to))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date_to format, use ISO 8601 (YYYY-MM-DD)",
            )

    total = query.count()
    videos = query.order_by(VideoModel.created_at.desc()).offset(offset).limit(limit).all()

    previews = [
        {
            "id": v.id,
            "title": v.title,
            "description": v.description,
            "file_name": v.file_name,
            "uploader": v.user.username if v.user else None,
            "created_at": v.created_at,
            "status": {"id": v.status.id, "status_name": v.status.status_name},
            "preview": None,  # search results skip heavy preview fetch
        }
        for v in videos
    ]

    return {"previews": previews, "total": total, "offset": offset, "limit": limit}
