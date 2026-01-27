from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from app.db.session import Base


class VideoStatusModel(Base):
    __tablename__ = "video_status"

    id = Column(Integer, primary_key=True, index=True)
    status_name = Column(String, unique=True, index=True)

    # Relación con los videos
    videos = relationship("VideoModel", back_populates="status")
