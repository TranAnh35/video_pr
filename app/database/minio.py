import logging
from minio import Minio
import tempfile
from app.config.settings import settings

logger = logging.getLogger(__name__)

class MinioStorage:
    _instance = None  # Singleton pattern
    
    @classmethod
    def get_instance(cls):
        """Singleton pattern to return a single instance of MinIO"""
        if cls._instance is None:
            cls._instance = MinioStorage()
        return cls._instance
    
    def __init__(self):
        """Initialize the Minio connection"""
        if MinioStorage._instance is not None:
            return
            
        self.client = None
        
        try:
            self.client = Minio(
                endpoint=settings.minio_endpoint,
                access_key=settings.ACCESS_KEY,
                secret_key=settings.SECRET_KEY,
                secure=False
            )
            logger.info("MinIO connection established")
        except Exception as e:
            logger.error(f"MinIO connection error: {e}")
            print("Continuing without MinIO connection...")
    
    def is_connected(self):
        """Check if the connection is available"""
        return self.client is not None
        
    def upload_object(self, bucket_name, image_key, image_path):
        """Upload file to MinIO"""
        if not self.is_connected():
            logger.error("No MinIO connection available. Can't upload file.")
            return False
    
        try:     
            if not self.client.bucket_exists(bucket_name):
                self.client.make_bucket(bucket_name)
    
            self.client.fput_object(bucket_name, image_key, image_path)

            logger.info("Upload file successfully")
            return True
        except Exception as e:
            logger.error(f"Exception in MinIO upload: {e}")
            return False
    
    def get_object(self, bucket_name, image_key):
        """Get file from MinIO and save to temporary path"""
        if not self.is_connected():
            logger.error("No MinIO connection available. Can't get file.")
            return None
    
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{image_key}") as temp_file:
                temp_file_path = temp_file.name
                
            self.client.fget_object(bucket_name, image_key, temp_file_path)
            
            logger.info("Image retrieved successfully")
            return temp_file_path
        except Exception as e:
            logger.error(f"Exception in MinIO get: {e}")
            return None


# Singleton instance
_storage_instance = None

def get_storage():
    """Get storage instance"""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = MinioStorage.get_instance()
    return _storage_instance    