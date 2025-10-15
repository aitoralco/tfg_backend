from fastapi import APIRouter, Depends, UploadFile, File, Header, HTTPException, status
from app.schemas.video_schema import VideoUploadResponse
from sqlalchemy.orm import Session
from app.services.video_service import save_video, get_video_stream
from app.models.video_model import VideoModel
from app.services.video_service import get_videos_previews
from app.schemas.video_schema import VideoPreviewsResponse


from app.db.session import SessionLocal

router = APIRouter(prefix="/videos", tags=["videos"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/upload", response_model=VideoUploadResponse)
async def upload_video(file: UploadFile = File(...), db: Session = Depends(get_db)):
    # Save the video metadata and write file to disk
    result = save_video(db, file, user_id=1, video_title=file.filename)
    return VideoUploadResponse(message="Video uploaded successfully", video_id=result.id)

@router.get("/previews", response_model=VideoPreviewsResponse)
def videos_previews(user_id: int = None, offset: int = 0, limit: int = 10, size: int = 1024, db: Session = Depends(get_db)):
    """Return base64 previews with pagination. limit default 10, max 50."""
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
