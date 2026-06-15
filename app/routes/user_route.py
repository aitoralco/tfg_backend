from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.schemas.user_schema import (
    UserCreate,
    UserRead,
    UserLogin,
    UserSelfUpdate,
    UserAdminUpdate,
    TokenResponse,
    RoleRead,
    RoleCreate,
)
from app.services.user_service import (
    create_user,
    get_user,
    login_user,
    get_all_users,
    self_update_user,
    admin_update_user,
    create_role_in_db,
    delete_db_user,
)
from app.core.security import create_access_token
from app.core.auth import get_current_user, get_current_admin
from app.models.user_model import UserModel
from app.db.session import get_db

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(user: UserCreate, db: Session = Depends(get_db)):
    return create_user(db, user)


@router.post("/login", response_model=TokenResponse)
async def login(user: UserLogin, db: Session = Depends(get_db)):
    db_user = login_user(db, user.username, user.password)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token(user_id=db_user.id, role=db_user.role.name)
    return TokenResponse(access_token=token, user=db_user)


@router.get("/me", response_model=UserRead)
async def get_me(current_user: UserModel = Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=UserRead)
async def update_me(
    update: UserSelfUpdate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    return self_update_user(db, current_user, update)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    update: UserSelfUpdate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    from app.services.user_service import verify_password
    if not verify_password(update.current_password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Incorrect password")
    delete_db_user(db, current_user.id)


# --- Admin-only endpoints ---

@router.get("/all", response_model=list[UserRead])
async def get_all(
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_admin),
):
    return get_all_users(db)


@router.get("/{user_id}", response_model=UserRead)
async def read_user(
    user_id: int,
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    db_user = get_user(db, user_id)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return db_user


@router.put("/{user_id}", response_model=UserRead)
async def admin_update(
    user_id: int,
    update: UserAdminUpdate,
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_admin),
):
    return admin_update_user(db, user_id, update)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete(
    user_id: int,
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_admin),
):
    if not delete_db_user(db, user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")


@router.post("/roles", response_model=RoleRead)
async def create_role(
    role: RoleCreate,
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_admin),
):
    return create_role_in_db(db, role)
