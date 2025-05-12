import os
import hashlib
from app.database.minio import get_storage, MinioStorage
import logging
from app.database.postgresql import get_db, save_image
from app.utils.image_metadata import extract_image_metadata
from app.config.setting import MINIO_CONFIG

import logging
logger = logging.getLogger(__name__)

class ImageConnector:
    _instance = None  # Singleton pattern
    
    @classmethod
    def get_instance(cls):
        """Singleton pattern để trả về instance duy nhất"""
        if cls._instance is None:
            cls._instance = ImageConnector()
        return cls._instance
    
    def __init__(self):
        """Khởi tạo connector"""
        if ImageConnector._instance is not None:
            # Nếu đã có instance, không tạo mới
            return
        
        self._image_cache = {}  # Cache cho các kết quả tìm kiếm
    
    def _calculate_file_hash(self, file_path):
        """
        Tính toán hash SHA-256 từ nội dung file
        
        Args:
            file_path: Đường dẫn đến file cần tính hash
            
        Returns:
            str: Chuỗi hex hash SHA-256 của file
        """
        sha256_hash = hashlib.sha256()
        
        # Đọc và hash file theo từng khối để xử lý file lớn hiệu quả
        with open(file_path, "rb") as f:
            # Đọc file theo từng khối 64kb
            for byte_block in iter(lambda: f.read(65536), b""):
                sha256_hash.update(byte_block)
                
        return sha256_hash.hexdigest()
    
    def upload_image_and_save_caption(self, image_path, caption):
        """
        Upload hình ảnh lên Minio và lưu thông tin vào PostgreSQL
        
        Args:
            image_path: Đường dẫn đến file hình ảnh
            caption: Caption cho hình ảnh
        
        Returns:
            str: ID của hình ảnh trên Minio hoặc None nếu thất bại
            str: "DUPLICATE:{unique_key}" nếu file đã tồn tại
        """
        try:
            if not os.path.exists(image_path):
                logger.error(f"File không tồn tại: {image_path}")
                return None
            
            file_name = os.path.basename(image_path)
            
            content_hash = self._calculate_file_hash(image_path)
            
            _, file_ext = os.path.splitext(file_name)
            if not file_ext:
                file_ext = ".jpg"  # Mặc định nếu không có phần mở rộng
            
            unique_key = f"{content_hash}{file_ext}"
            
            skip_check = os.environ.get("SKIP_DUPLICATE_CHECK", "0") == "1"
            
            if not skip_check:
                db = get_db()
                if db.is_connected():
                    exists = db.check_image_exists(unique_key)
                    if exists:
                        logger.info(f"Hình ảnh '{file_name}' đã tồn tại trong database với hash: {content_hash}")
                        db.add_caption_to_image(unique_key, caption)
                        return f"DUPLICATE:{unique_key}"
            
            storage = MinioStorage.get_instance()
            success = storage.upload_object(MINIO_CONFIG["bucket_name"], unique_key, image_path)
            
            if not success:
                logger.error(f"Không thể upload hình ảnh: {image_path}")
                return None
            
            metadata = extract_image_metadata(image_path)
            
            save_image(unique_key, metadata, caption)
            logger.info(f"Đã upload và lưu metadata cho ảnh: {unique_key}")
            
            return unique_key
        except Exception as e:
            logger.error(f"Lỗi khi upload hình ảnh và lưu caption: {e}")
            return None
    
    def get_image(self, query):
        """Lấy hình ảnh từ database dựa trên caption hoặc image_key"""
        
        if len(query) > 40 and '.' in query:
            storage = get_storage()
            image_path = storage.get_object(MINIO_CONFIG["bucket_name"], query)
            
            if image_path:
                self._image_cache[query] = image_path
                logger.info(f"Lấy ảnh trực tiếp theo image_key: {query}")
            else:
                logger.warning(f"Không tìm thấy ảnh với image_key: {query}")
            
            return image_path
        
        if query in self._image_cache:
            cache_path = self._image_cache[query]
            if os.path.exists(cache_path):
                result = cache_path
                logger.info(f"Image cache hit: Sử dụng hình ảnh từ cache: {cache_path}")
                return result
            else:
                del self._image_cache[query]
                logger.warning(f"Cache bị stale, file không còn tồn tại: {cache_path}")
        
        db = get_db()
        storage = get_storage()
        
        results = db.search_image_by_caption(query)
        
        if not results:
            logger.warning(f"Không tìm thấy ảnh phù hợp với caption: '{query}'")
            return None
        
        image_key = results[0][1]
        logger.info(f"Tìm thấy ảnh với key: {image_key}")
        
        image_path = storage.get_object(MINIO_CONFIG["bucket_name"], image_key)
        
        if image_path:
            self._image_cache[query] = image_path
            logger.info(f"Đã lấy ảnh từ MinIO và cache lại với caption: '{query}'")
        else:
            logger.error(f"Không lấy được ảnh từ MinIO với key: {image_key}")
        
        return image_path


# ---------- Compatibility functions for existing code ----------

# Singleton instance
_connector_instance = None

def get_connector():
    """Get connector instance"""
    global _connector_instance
    if _connector_instance is None:
        _connector_instance = ImageConnector.get_instance()
    return _connector_instance

def upload_image_and_save_caption(image_path, caption):
    """Upload image and save caption (compatibility function)"""
    return get_connector().upload_image_and_save_caption(image_path, caption)

def get_image(caption):
    """Get image by caption (compatibility function)"""
    return get_connector().get_image(caption)