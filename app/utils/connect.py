import os
import hashlib
from app.database.minio import get_storage
import logging
from app.database.postgresql import get_db
from app.utils.image_metadata import extract_image_metadata
from app.config.settings import settings

import logging
logger = logging.getLogger(__name__)

class ImageConnector:
    _instance = None  # Singleton pattern
    
    @classmethod
    def get_instance(cls):
        """Singleton pattern to return a single instance"""
        if cls._instance is None:
            cls._instance = ImageConnector()
        return cls._instance
    
    def __init__(self):
        """Initialize the connector"""
        if ImageConnector._instance is not None:
            return
        
        self.storage = get_storage()
        self.db = get_db()
        self._image_cache = {}
    
    def _calculate_file_hash(self, file_path):
        """
        Calculate SHA-256 hash from file content
        
        Args:
            file_path: Path to the file to calculate hash
            
        Returns:
            str: Hex SHA-256 hash of the file
        """
        sha256_hash = hashlib.sha256()
        
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(65536), b""):
                sha256_hash.update(byte_block)
                
        return sha256_hash.hexdigest()
    
    def upload_image_and_save_caption(self, image_path, caption):
        """
        Upload image to Minio and save caption to PostgreSQL
        
        Args:
            image_path: Path to the image file
            caption: Caption for the image
        
        Returns:
            str: ID of the image on Minio or None if failed
            str: "DUPLICATE_IMAGE:{unique_key}" if image already exists
            str: "DUPLICATE_CAPTION:{caption}" if caption already exists
        """
        try:
            if not os.path.exists(image_path):
                logger.error(f"File does not exist: {image_path}")
                return None
            
            # First check if caption already exists for any image
            if self.db.is_connected():
                caption_exists = self.db.check_caption_exists(caption)
                if caption_exists:
                    logger.info(f"Caption '{caption}' already exists in database")
                    return f"DUPLICATE_CAPTION:{caption}"
            
            file_name = os.path.basename(image_path)
            
            content_hash = self._calculate_file_hash(image_path)
            
            _, file_ext = os.path.splitext(file_name)
            if not file_ext:
                file_ext = ".jpg"  # Mặc định nếu không có phần mở rộng
            
            unique_key = f"{content_hash}{file_ext}"
            
            skip_check = os.environ.get("SKIP_DUPLICATE_CHECK", "0") == "1"
            
            if not skip_check:
                if self.db.is_connected():
                    exists = self.db.check_image_exists(unique_key)
                    if exists:
                        logger.info(f"Image '{file_name}' already exists in database with hash: {content_hash}")
                        # We don't need to add caption since we've already checked it's not a duplicate
                        return f"DUPLICATE_IMAGE:{unique_key}"
            
            success = self.storage.upload_object(settings.BUCKET_NAME, unique_key, image_path)
            
            if not success:
                logger.error(f"Failed to upload image: {image_path}")
                return None
            
            metadata = extract_image_metadata(image_path)
            
            self.db.save_image(unique_key, metadata, caption)
            logger.info(f"Image uploaded and metadata saved: {unique_key}")
            
            return unique_key
        except Exception as e:
            logger.error(f"Failed to upload image and save caption: {e}")
            return None
    
    def get_image(self, query):
        """Get image from database based on caption or image_key"""
        logger.info(f"Getting image for query: {query}")
        
        if len(query) > 40 and '.' in query:
            image_path = self.storage.get_object(settings.BUCKET_NAME, query)
            
            if image_path:
                self._image_cache[query] = image_path
                logger.info(f"Image retrieved directly by image_key: {query}")
            else:
                logger.warning(f"Image not found with image_key: {query}")
            
            return image_path
        
        if query in self._image_cache:
            cache_path = self._image_cache[query]
            if os.path.exists(cache_path):
                result = cache_path
                logger.info(f"Image cache hit: Using cached image: {cache_path}")
                return result
            else:
                del self._image_cache[query]
                logger.warning(f"Cache stale, file no longer exists: {cache_path}")
        
        results = self.db.search_image_by_caption(query)
        
        if not results:
            logger.warning(f"Image not found with caption: '{query}'")
            return None
        
        image_key = results[0][1]
        logger.info(f"Found image with key: {image_key}")
        
        image_path = self.storage.get_object(settings.BUCKET_NAME, image_key)
        
        if image_path:
            self._image_cache[query] = image_path
            logger.info(f"Image retrieved from MinIO and cached with caption: '{query}'")
        else:
            logger.error(f"Failed to retrieve image from MinIO with key: {image_key}")
        
        return image_path

# Singleton instance
_connector_instance = None

def get_connector():
    """Get connector instance"""
    global _connector_instance
    if _connector_instance is None:
        _connector_instance = ImageConnector.get_instance()
    return _connector_instance