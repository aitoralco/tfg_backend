from fastapi import FastAPI
from app.routes.routes import router as api_router
from app.routes.video_route import router as video_router
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI(title="Cetaceans Backend 🐳", version="1.0.0")

origins = [
    "http://localhost",
    "http://localhost:8000",
    "http://localhost:3000",
    "http://localhost:4200"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,       # o ["*"] en desarrollo
    allow_credentials=True,
    allow_methods=["*"],         # permite OPTIONS, POST, GET, ...
    allow_headers=["*"],         # permite headers personalizados
)

app.include_router(api_router)
app.include_router(video_router)