from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models.user_model import UserModel
from app.models.role_model import RoleModel
from app.schemas.user_schema import UserCreate, UserRead, RoleCreate, UserSelfUpdate, UserAdminUpdate
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_user(db: Session, user: UserCreate) -> UserModel:
    db_user = UserModel(
        username=user.username,
        email=user.email,
        password_hash=get_password_hash(user.password),
        role_id=2,  # default: regular user
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def get_user(db: Session, user_id: int) -> UserModel | None:
    return db.query(UserModel).filter(UserModel.id == user_id).first()


def login_user(db: Session, username: str, password: str) -> UserModel | None:
    user = db.query(UserModel).filter(UserModel.username == username).first()
    if user and verify_password(password, user.password_hash):
        return user
    return None


def get_all_users(db: Session) -> list[UserRead]:
    return db.query(UserModel).all()


def self_update_user(db: Session, user: UserModel, update: UserSelfUpdate) -> UserModel:
    """Regular user updates their own data — current password is mandatory."""
    if not verify_password(update.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Incorrect current password",
        )

    if update.username is not None:
        user.username = update.username
    if update.email is not None:
        user.email = update.email
    if update.new_password is not None:
        user.password_hash = get_password_hash(update.new_password)

    db.commit()
    db.refresh(user)
    return user


def admin_update_user(db: Session, user_id: int, update: UserAdminUpdate) -> UserModel:
    """Admin updates any user — no password verification, role changes allowed."""
    user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if update.username is not None:
        user.username = update.username
    if update.email is not None:
        user.email = update.email
    if update.password is not None:
        user.password_hash = get_password_hash(update.password)
    if update.role_id is not None:
        user.role_id = update.role_id

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


def create_role_in_db(db: Session, role: RoleCreate) -> RoleModel:
    db_role = RoleModel(id=role.role_id, name=role.name)
    db.add(db_role)
    db.commit()
    db.refresh(db_role)
    return db_role
