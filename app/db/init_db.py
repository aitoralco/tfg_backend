from app.db.session import Base, engine
import app.models  # registers all models (user, role, video, video_status) with Base

Base.metadata.create_all(bind=engine)

print("Database initialized with all tables.")