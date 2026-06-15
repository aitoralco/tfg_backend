from fastapi import APIRouter, Depends, UploadFile, File, Header, HTTPException, status, Form
from sqlalchemy.orm import Session
from typing import Optional

from app.schemas.video_schema import (
    VideoUploadResponse,
    VideoRead,
    VideoUpdate,
    VideoPreviewsResponse,
    CreateVideoStatusResponse,
    VideoInfoResponse,
    CropsPageResponse,
)
from app.services.video_service import (
    save_video,
    get_video_stream,
    get_videos_previews,
    get_my_videos,
    search_videos,
    create_video_status,
    update_video,
    delete_video,
    get_video_info,
    get_dw_stream,
    get_ew_crops,
    get_dem_crops,
)
from app.models.video_model import VideoModel
from app.core.auth import get_current_user
from app.models.user_model import UserModel
from app.db.session import get_db

router = APIRouter(prefix="/videos", tags=["videos"])


# --- Public endpoints (no auth required) ---

@router.get("/{video_id}/info", response_model=VideoInfoResponse)
def video_info(video_id: int, db: Session = Depends(get_db)):
    """Full metadata + processing phase summary for a single video."""
    return get_video_info(db, video_id)


@router.get("/{video_id}/dw/stream")
def stream_dw_video(
    video_id: int,
    range: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """Stream the DW annotated video with Range support."""
    return get_dw_stream(db, video_id, range)


@router.get("/{video_id}/ew/crops", response_model=CropsPageResponse)
def ew_crops(
    video_id: int,
    offset: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    """Paginated presigned URLs for EW whale crops."""
    return get_ew_crops(db, video_id, offset, limit)


@router.get("/{video_id}/dem/crops", response_model=CropsPageResponse)
def dem_crops(
    video_id: int,
    offset: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    """Paginated presigned URLs for DEM crops."""
    return get_dem_crops(db, video_id, offset, limit)


@router.get("/previews", response_model=VideoPreviewsResponse)
def videos_previews(
    user_id: Optional[int] = None,
    offset: int = 0,
    limit: int = 10,
    size: int = 1024,
    db: Session = Depends(get_db),
):
    """Paginated list of videos with first-bytes preview for the home page."""
    result = get_videos_previews(db, user_id=user_id, offset=offset, limit=limit, size=size)
    return result


@router.get("/search", response_model=VideoPreviewsResponse)
def search(
    q: Optional[str] = None,
    uploader: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    offset: int = 0,
    limit: int = 10,
    db: Session = Depends(get_db),
):
    """Search videos by title, description, uploader username, or date range."""
    result = search_videos(db, q=q, uploader=uploader, date_from=date_from, date_to=date_to, offset=offset, limit=limit)
    return result


@router.get("/mine", response_model=VideoPreviewsResponse)
def my_videos(
    offset: int = 0,
    limit: int = 10,
    q: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    status_id: Optional[int] = None,
    sort_by: str = "created_at",
    order: str = "desc",
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    """All videos belonging to the current user, including private ones. Supports filtering and sorting."""
    return get_my_videos(db, current_user.id, offset, limit, q, date_from, date_to, status_id, sort_by, order)


@router.get("/{video_id}")
def stream_video(
    video_id: int,
    range: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """Stream video with Range request support (progressive playback)."""
    video = db.query(VideoModel).filter(VideoModel.id == video_id).first()
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    return get_video_stream(video, range)


# --- Authenticated endpoints ---

@router.post("/upload", response_model=VideoUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_video(
    video_name: str = Form(...),
    description: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    """Upload a video directly to MinIO. Auth required."""
    result = save_video(
        db,
        file,
        user_id=current_user.id,
        video_title=video_name,
        video_description=description,
    )
    return VideoUploadResponse(message="Video uploaded successfully", video_id=result.id)


@router.patch("/{video_id}", response_model=VideoRead)
def update_video_endpoint(
    video_id: int,
    update: VideoUpdate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    """Update a video's title, description, or shared status. Owner only."""
    return update_video(db, video_id, update, current_user.id)


@router.delete("/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_video_endpoint(
    video_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    """Delete a video and its file from storage. Owner only."""
    delete_video(db, video_id, current_user.id)


# --- Admin / debug endpoints ---

@router.post("/create_status", response_model=CreateVideoStatusResponse)
async def create_status(
    status_name: str,
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),  # at minimum logged in
):
    result = create_video_status(db, status_name)
    return CreateVideoStatusResponse(id=result.id, status_name=result.status_name)


@router.get("/meta/{video_id}", response_model=VideoUploadResponse)
def video_meta(video_id: int, db: Session = Depends(get_db)):
    """Debug: return minimal metadata about a video record."""
    video = db.query(VideoModel).filter(VideoModel.id == video_id).first()
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    return {"message": "found", "video_id": video.id}


@router.put("/enqueue_test")
def enqueue_test():
    """Debug: enqueue a test Redis job."""
    from app.cache_redis.redis_engine import RedisEngine
    from app.cache_redis.tasks import worker_test
    import time

    redis_engine = RedisEngine()
    redis_engine.enqueue_job(worker_test, f"Hello from api at {time.time()}")
    return {"message": "Test job enqueued"}
