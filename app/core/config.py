import os

class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL", "localhost:5432")

settings = Settings()