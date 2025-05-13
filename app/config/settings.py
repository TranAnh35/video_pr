import os
from pathlib import Path
from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import enum

class LogLevel(str, enum.Enum):
    """Possible log levels."""

    NOTSET = "NOTSET"
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    FATAL = "FATAL"

# Check environment
app_env = os.getenv("APP_ENV", "local")

# Load appropriate .env file
if app_env == "docker":
    env_path = Path(__file__).resolve().parents[3] / '.env.docker'
else:
    env_path = Path(__file__).resolve().parents[3] / '.env.local'

# Fallback to .env if specific file doesn't exist
if not env_path.exists():
    env_path = Path(__file__).resolve().parents[3] / '.env'

load_dotenv(dotenv_path=env_path)

class Settings(BaseSettings):
    
    domain: str = ""
    host: str = "0.0.0.0" if os.getenv("APP_ENV") == "docker" else "127.0.0.1"
    port: int = 8000
    reload: bool = False
    workers_count: int = 1
    
    log_level: LogLevel = LogLevel.INFO
    
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