from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class VideoStatusRead(BaseModel):
    id: int
    status_name: str

    model_config = {"from_attributes": True}


class VideoRead(BaseModel):
    id: int
    user_id: int
    title: str
    file_name: Optional[str] = None
    description: Optional[str] = None
    shared: bool
    status: VideoStatusRead
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


class VideoUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    shared: Optional[bool] = None


class VideoPreview(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    file_name: Optional[str] = None
    uploader: Optional[str] = None
    created_at: Optional[datetime] = None
    status: Optional[VideoStatusRead] = None
    preview: Optional[str] = None


class VideoPreviewsResponse(BaseModel):
    previews: List[VideoPreview]
    total: int
    offset: int
    limit: int

    model_config = {"from_attributes": True}


class CreateVideoStatusResponse(BaseModel):
    id: int
    status_name: str


# --- Video detail / processing phases ---

class ClassEntry(BaseModel):
    count: int
    percentage: float
    avg_confidence: float


class ClassificationResult(BaseModel):
    total_images: int
    classified_images: int
    errors: int
    classes: dict[str, ClassEntry]


class DWPhaseInfo(BaseModel):
    available: bool
    video_key: Optional[str] = None
    label_count: int = 0


class EWPhaseInfo(BaseModel):
    available: bool
    crop_count: int = 0


class DEMPhaseInfo(BaseModel):
    available: bool
    txt_count: int = 0
    crop_count: int = 0


class VideoInfoResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    uploader: Optional[str] = None
    created_at: Optional[datetime] = None
    status: VideoStatusRead
    shared: bool
    thumbnail: Optional[str] = None  # base64 JPEG
    dw: DWPhaseInfo
    ew: EWPhaseInfo
    dem: DEMPhaseInfo
    classification: Optional[ClassificationResult] = None


class CropItem(BaseModel):
    key: str
    url: str


class CropsPageResponse(BaseModel):
    crops: List[CropItem]
    total: int
    offset: int
    limit: int
