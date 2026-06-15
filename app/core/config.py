from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import computed_field

class Settings(BaseSettings):
    # Postgres Database settings
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_SERVER: str
    POSTGRES_PORT: int
    POSTGRES_DB: str
    DEBUG: bool = False # Valor por defecto para NO mostrar las queries en debug terminal

        # construir url
    @computed_field
    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # Redis settings
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_DB: int
    REDIS_PASSWORD: str

    # JWT settings
    JWT_SECRET_KEY: str

    # Minio settings
    FILESYSTEM_URL: str
    FILESYSTEM_ACCESS_KEY: str
    FILESYSTEM_ID_KEY: str
    FORCE_PATH_STYLE: bool
    REGION_NAME: str
    BUCKET_NAME: str

    # Pydantic busca en el .env
    model_config = SettingsConfigDict(env_file=".env", env_file_encodings="utf-8")

settings = Settings()