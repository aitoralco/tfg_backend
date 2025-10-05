from fastapi import FastAPI
from app.routes.routes import router as api_router


app = FastAPI(title="Cetaceans Backend 🐳", version="1.0.0")

app.include_router(api_router)