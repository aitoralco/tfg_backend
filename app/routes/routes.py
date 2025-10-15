from fastapi import APIRouter
from app.routes import user_route, video_route

router = APIRouter()

router.include_router(user_route.router)
router.include_router(video_route.router)
