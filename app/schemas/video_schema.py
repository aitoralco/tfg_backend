from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from typing import List

# For reading video data
class VideoRead(BaseModel):
    id: int
    user_id: int
    title: str
    file_name: Optional[str] = None
    processed: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

class VideoUploadResponse(BaseModel):
    message: str
    video_id: Optional[int] = None

class VideoCreate(BaseModel):
    user_id: int
    title: str
    file_name: Optional[str] = None
    processed: bool = False


class VideoPreview(BaseModel):
    id: int
    title: str
    file_name: Optional[str] = None
    # base64-encoded initial bytes (or None if missing)
    preview: Optional[str] = None


class VideoPreviewsResponse(BaseModel):
    previews: List[VideoPreview]

    model_config = {"from_attributes": True}


# For video status
class CreateVideoStatusResponse(BaseModel):
    id: int
    status_name: str
