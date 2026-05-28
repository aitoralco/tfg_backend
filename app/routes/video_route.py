from fastapi import APIRouter, Depends, UploadFile, File, Header, HTTPException, status, Form
from app.schemas.video_schema import VideoUploadResponse
from sqlalchemy.orm import Session
from app.services.video_service import save_video, get_video_stream
from app.models.video_model import VideoModel
from app.services.video_service import get_videos_previews, create_video_status
from app.schemas.video_schema import VideoPreviewsResponse, CreateVideoStatusResponse
from app.db.session import get_db

router = APIRouter(prefix="/videos", tags=["videos"])


@router.post("/create_status", response_model=CreateVideoStatusResponse)
async def create_status(status_name: str, db: Session = Depends(get_db)):
    #create a new status
    result = create_video_status(db, status_name)
    return CreateVideoStatusResponse(id=result.id, status_name=result.status_name)


@router.post("/upload", response_model=VideoUploadResponse)
async def upload_video( user_id: int = Form(...), 
                        video_name: str = Form(...), 
                        description: str = Form(...), 
                        file: UploadFile = File(...), 
                        db: Session = Depends(get_db)
                        ):
    # Save the video metadata and write file to disk
    #print("upload_video called with user_id:", user_id)
    user_id = int(user_id)
    if user_id == 0:
        # error
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="user_id is required")
    result = save_video(db, file, user_id=user_id, video_title=video_name, video_description=description)
    return VideoUploadResponse(message="Video uploaded successfully", video_id=result.id)


@router.get("/previews", response_model=VideoPreviewsResponse)
def videos_previews(user_id: str = None, offset: int = 0, limit: int = 10, size: int = 1024, db: Session = Depends(get_db)):
    """Return base64 previews with pagination. limit default 10, max 50."""
    user_id = int(user_id) if user_id is not None else None
    previews = get_videos_previews(db, user_id=user_id, offset=offset, limit=limit, size=size)
    return {"previews": previews}


@router.get("/meta/{video_id}", response_model=VideoUploadResponse)
def video_meta(video_id: int, db: Session = Depends(get_db)):
    """Debug endpoint: return minimal metadata about a video record."""
    video = db.query(VideoModel).filter(VideoModel.id == video_id).first()
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    # include file existence info could be added here; minimal response for debug
    return {"message": "found", "video_id": video.id}


@router.get("/{video_id}")
def stream_video(video_id: int, range: str | None = Header(None), db: Session = Depends(get_db)):
    """
    Stream video supporting Range requests so the frontend can play it progressively.
    Busca el video en la BD (por id) y devuelve el StreamingResponse desde get_video_stream().
    """
    video = db.query(VideoModel).filter(VideoModel.id == video_id).first()
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    # video.file_name debe ser el nombre único que guardaste al subir
    return get_video_stream(video.file_name, range)


@router.put("/enqueue_test")
def enqueue_test(db: Session = Depends(get_db)):
    """Debug endpoint: create a dummy video record and enqueue a processing job for it."""
    from app.cache_redis.redis_engine import RedisEngine
    from app.cache_redis.tasks import worker_test
    import time

    # Create dummy video record
    #dummy_video = VideoModel(
    #    user_id=1,
    #    title="Test Video",
    #    file_name="test_video.mp4"
    #)
    #db.add(dummy_video)
    #db.commit()
    #db.refresh(dummy_video)

    # Enqueue processing job
    redis_engine = RedisEngine()

    now_time = time.time()

    text = f"Hello from api at {now_time}"

    redis_engine.enqueue_job(worker_test, text)

    return {"message": "Test video record created and job enqueued"}