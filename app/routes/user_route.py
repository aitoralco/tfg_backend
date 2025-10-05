from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.schemas.user_schema import UserCreate, UserRead, UserLogin
from app.services.user_service import create_user, get_user, login_user
from app.db.session import SessionLocal

router = APIRouter(prefix="/users", tags=["users"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/", response_model=UserRead)
async def create_new_user(user: UserCreate, db: Session = Depends(get_db)):
    return create_user(db, user)



@router.get("/{user_id}", response_model=UserRead)
async def read_user(user_id: int, db: Session = Depends(get_db)):
    db_user = get_user(db, user_id)
    if db_user is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="User not found")
    return db_user


@router.post("/login", response_model=UserRead)
async def login(user: UserLogin, db: Session = Depends(get_db)):
    user = login_user(db, user.username, user.password)
    if user is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Invalid credentials")
    return user