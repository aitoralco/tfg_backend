from fastapi import APIRouter
from app.routes import user_route

router = APIRouter()

router.include_router(user_route.router)
