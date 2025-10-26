from fastapi import APIRouter, Depends
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.schemas.user_schema import UserCreate, UserRead, UserLogin, UserUpdate
from app.services.user_service import create_user, get_user, login_user, get_all_users, update_db_user
from app.db.session import SessionLocal

router = APIRouter(prefix="/users", tags=["users"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/login", response_model=UserRead)
async def login(user: UserLogin, db: Session = Depends(get_db)):
    user = login_user(db, user.username, user.password)
    if user is None:
        raise HTTPException(status_code=400, detail="Invalid credentials")
    return user


@router.post("/register", response_model=UserRead)
async def create_new_user(user: UserCreate, db: Session = Depends(get_db)):
    return create_user(db, user)


@router.get("/get_all_users", response_model=list[UserRead])
async def get_users(db: Session = Depends(get_db)):
    return get_all_users(db)


@router.get("/{user_id}", response_model=UserRead)
async def read_user(user_id: int, db: Session = Depends(get_db)):
    db_user = get_user(db, user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user


@router.post("/{user_id}", response_model=UserRead)
async def update_user(user_id: int, user: UserUpdate, db: Session = Depends(get_db)):
    return update_db_user(db, user_id, user)


@router.delete("/{user_id}")
async def delete_user(user_id: int, db: Session = Depends(get_db)):
    
    success = delete_db_user(db, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="User not found")
    return {"detail": "User deleted successfully"}