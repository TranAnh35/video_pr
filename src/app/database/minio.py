from minio import Minio
import tempfile
from app.config.setting import MINIO_CONFIG


class MinioStorage:
    _instance = None  # Singleton pattern
    
    @classmethod
    def get_instance(cls):
        """Singleton pattern để trả về instance duy nhất của storage"""
        if cls._instance is None:
            cls._instance = MinioStorage()
        return cls._instance
    
    def __init__(self):
        """Khởi tạo kết nối MinIO"""
        if MinioStorage._instance is not None:
            # Nếu đã có instance, không tạo mới
            return
            
        self.client = None
        
        try:
            self.client = Minio(
                endpoint=MINIO_CONFIG["endpoint"],
                access_key=MINIO_CONFIG["access_key"],
                secret_key=MINIO_CONFIG["secret_key"],
                secure=MINIO_CONFIG["secure"]
            )
            print("MinIO connection established")
        except Exception as e:
            print(f"MinIO connection error: {e}")
            print("Continuing without MinIO connection...")
    
    def is_connected(self):
        """Kiểm tra kết nối có khả dụng không"""
        return self.client is not None
    
    def upload_object(self, bucket_name, image_key, image_path):
        """Upload file lên MinIO"""
        if not self.is_connected():
            print("No MinIO connection available. Can't upload file.")
            return False
    
        try:     
            if not self.client.bucket_exists(bucket_name):
                self.client.make_bucket(bucket_name)
    
            self.client.fput_object(bucket_name, image_key, image_path)

            print("Upload thành công")
            return True
        except Exception as e:
            print(f"Exception in MinIO upload: {e}")
            return False
        
    def get_object(self, bucket_name, image_key):
        """Lấy file từ MinIO và lưu vào đường dẫn tạm"""
        if not self.is_connected():
            print("No MinIO connection available. Can't get file.")
            return None
    
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{image_key}") as temp_file:
                temp_file_path = temp_file.name
                
            # Lấy file từ MinIO và lưu vào đường dẫn tạm
            self.client.fget_object(bucket_name, image_key, temp_file_path)
            
            print("Ảnh đã được lấy thành công")
            return temp_file_path
        except Exception as e:
            print(f"Exception in MinIO get: {e}")
            return None


# ---------- Compatibility functions for existing code ----------

# Singleton instance
_storage_instance = None

def get_storage():
    """Get storage instance"""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = MinioStorage.get_instance()
    return _storage_instance

# Biến tương thích với code cũ
minio_client = None  # Được sử dụng bởi code cũ, nhưng không còn cần thiết

def upload_object(bucket_name, image_key, image_path):
    """Upload object (compatibility function)"""
    return get_storage().upload_object(bucket_name, image_key, image_path)

def get_object(bucket_name, image_key):
    """Get object (compatibility function)"""
    return get_storage().get_object(bucket_name, image_key)
        