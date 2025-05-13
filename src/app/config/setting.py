import os
from pathlib import Path
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parents[3] / '.env'
load_dotenv(dotenv_path=env_path)

class Settings(BaseSettings):
    # MinIO Configuration
    ACCESS_KEY: str = os.getenv("ACCESS_KEY", "")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    BUCKET_NAME: str = os.getenv("BUCKET_NAME", "")
    MINIO_HOST: str = os.getenv("MINIO_HOST", "localhost")
    MINIO_PORT: str = os.getenv("MINIO_PORT", "9000")
    
    # Database Configuration
    DB_NAME: str = os.getenv("DB_NAME", "")
    DB_USER: str = os.getenv("DB_USER", "")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: str = os.getenv("DB_PORT", "5432")
    
    # MinIO endpoint
    @property
    def minio_endpoint(self):
        return f"{self.MINIO_HOST}:{self.MINIO_PORT}"

settings = Settings()