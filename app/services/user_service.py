from sqlalchemy.orm import Session
from app.models.user_model import UserModel
from app.models.role_model import RoleModel
from app.schemas.user_schema import UserCreate, UserRead, RoleRead, UserUpdate, RoleCreate
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
        "role_id": 2 # 2 is default for regular user
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


def update_db_user(db: Session, user_id: int, user_update: UserUpdate) -> UserRead | None:
    user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not user:
        return None

    update_data = user_update.dict(exclude_unset=True)


    if not update_data:
        return user

    if "password" in update_data:
        hashed_password = get_password_hash(update_data.pop("password"))
        update_data["password_hash"] = hashed_password
        if "password" in update_data:
            del update_data["password"]

    for key, value in update_data.items():
        setattr(user, key, value)

    db.commit()
    db.refresh(user)
    return user


def delete_db_user(db: Session, user_id: int) -> bool:
    user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if user:
        db.delete(user)
        db.commit()
        return True
    return False


def create_role_in_db(db: Session, role: RoleCreate) -> RoleRead:
    role_data = role.dict()
    
    actual_id = role_data.pop("role_id", None) or role_data.pop("role_number", None)

    db_role = RoleModel(
        id=actual_id,
        name=role_data["name"]
    )

    db.add(db_role)
    db.commit()
    db.refresh(db_role)
    return db_role