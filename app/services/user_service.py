from sqlalchemy.orm import Session
from app.models.user_model import UserModel
from app.schemas.user_schema import UserCreate, UserRead
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_user(db: Session, user: UserCreate):
    hashed_password = get_password_hash(user.password)
    
    new_user = {
        "username": user.username,
        "email": user.email,
        "password_hash": hashed_password,
        "role": 0
    }

    db_user = UserModel(**new_user)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def get_user(db: Session, user_id: int) -> UserRead | None:
    return db.query(UserModel).filter(UserModel.id == user_id).first()


def login_user(db: Session, username: str, password: str) -> UserRead | None:
    user = db.query(UserModel).filter(UserModel.username == username).first()
    if user and pwd_context.verify(password, user.password_hash):
        return user
    return None


def get_all_users(db: Session) -> list[UserRead]:
    return db.query(UserModel).all()