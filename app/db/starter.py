"""
Script to INSERT starter base data into the DB
"""

from passlib.context import CryptContext

from app.db.session import get_db
from app.models.role_model import RoleModel
from app.models.video_status_model import VideoStatusModel
from app.models.user_model import UserModel
from sqlalchemy.orm import Session

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

db_generator = get_db()
db: Session = next(db_generator)

ROLES = ["admin", "user", "test"]
VIDEO_STATUS = [
    "error", 
    "unprocessed", 
    "processing_0",
    "processing_dw",
    "processing_ew",
    "processing_dem",
    "processed"
    ]

# Insert base roles
def base_roles():
    for role in ROLES:
        # Mirar si existe el rol
        exists = db.query(RoleModel).filter(RoleModel.name == role).first()

        # si no existe insert
        if not exists:
            new_role= {
                "name": role
            }
            db_role = RoleModel(**new_role)
            db.add(db_role)
            print(f"Role: [{role}] Inserted.")
        else:
            print(f"Role: [{role}] Already exists.")
    db.commit()

# Insert base video statuses
def base_video_status():
    for video_status in VIDEO_STATUS:
        # Mirar si existe el estado de video
        exists = db.query(VideoStatusModel).filter(
            VideoStatusModel.status_name == video_status
            ).first()

        # si no existe insert
        if not exists:
            new_video_status= {
                "status_name": video_status
            }
            db_video_status = VideoStatusModel(**new_video_status)
            db.add(db_video_status)
            print(f"Video Status: [{video_status}] Inserted.")
        else:
            print(f"Video Status: [{video_status}] Already exists.")
    db.commit()


# Insert default admin user
def base_admin_user():
    exists = db.query(UserModel).filter(UserModel.username == "admin").first()
    if not exists:
        admin_role = db.query(RoleModel).filter(RoleModel.name == "admin").first()
        db_user = UserModel(
            username="admin",
            email="admin@admin.com",
            password_hash=pwd_context.hash("admin"),
            role_id=admin_role.id,
        )
        db.add(db_user)
        db.commit()
        print("User: [admin] Inserted.")
    else:
        print("User: [admin] Already exists.")


# Main
if __name__ == "__main__":
    print("Inserting default DB data")
    base_roles()
    base_video_status()
    base_admin_user()