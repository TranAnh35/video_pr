import os
import hashlib
from app.database.minio import get_storage, MinioStorage
from app.database.postgresql import get_db, save_image
from app.utils.image_metadata import extract_image_metadata


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
            # Kiểm tra file tồn tại
            if not os.path.exists(image_path):
                print(f"File không tồn tại: {image_path}")
                return None
            
            # Lấy tên file để hiển thị log
            file_name = os.path.basename(image_path)
            
            # Tính toán content hash từ nội dung file
            content_hash = self._calculate_file_hash(image_path)
            
            # Lấy phần mở rộng của file để giữ lại trong key
            _, file_ext = os.path.splitext(file_name)
            if not file_ext:
                file_ext = ".jpg"  # Mặc định nếu không có phần mở rộng
            
            # Tạo unique key dựa trên content hash
            unique_key = f"{content_hash}{file_ext}"
            
            # Kiểm tra xem cần bỏ qua việc kiểm tra trùng lặp không
            skip_check = os.environ.get("SKIP_DUPLICATE_CHECK", "0") == "1"
            
            # Kiểm tra xem file đã tồn tại trong database chưa
            if not skip_check:
                db = get_db()
                if db.is_connected():
                    exists = db.check_image_exists(unique_key)
                    if exists:
                        print(f"Hình ảnh '{file_name}' đã tồn tại trong database với hash: {content_hash}")
                        
                        # Thêm caption mới cho ảnh đã tồn tại
                        db.add_caption_to_image(unique_key, caption)
                        
                        return f"DUPLICATE:{unique_key}"
            
            # Upload lên Minio nếu chưa tồn tại
            storage = MinioStorage.get_instance()
            success = storage.upload_object("images", unique_key, image_path)
            
            if not success:
                print(f"Không thể upload hình ảnh: {image_path}")
                return None
            
            # Lấy metadata
            metadata = extract_image_metadata(image_path)
            
            # Lưu vào PostgreSQL
            save_image(unique_key, metadata, caption)
            
            return unique_key
        except Exception as e:
            print(f"Lỗi khi upload hình ảnh và lưu caption: {e}")
            return None
    
    def get_image(self, query):
        """Lấy hình ảnh từ database dựa trên caption hoặc image_key"""
        
        # Nếu query có vẻ như là một image_key (dạng hash + extension)
        if len(query) > 40 and '.' in query:
            # Lấy thẳng từ MinIO
            storage = get_storage()
            image_path = storage.get_object("images", query)
            
            # Cập nhật cache nếu tìm thấy
            if image_path:
                self._image_cache[query] = image_path
            
            return image_path
        
        # Kiểm tra xem caption đã có trong cache chưa
        if query in self._image_cache:
            cache_path = self._image_cache[query]
            # Kiểm tra xem file cache còn tồn tại không
            if os.path.exists(cache_path):
                result = cache_path
                print(f"Image cache hit: Sử dụng hình ảnh từ cache: {cache_path}")
                return result
            else:
                # Nếu file không tồn tại, xóa khỏi cache
                del self._image_cache[query]
        
        db = get_db()
        storage = get_storage()
        
        # Tìm kiếm hình ảnh theo caption - thời gian được đo trong hàm search_image_by_caption
        results = db.search_image_by_caption(query)
        
        # Kiểm tra xem có kết quả trả về không
        if not results:
            print(f"Không tìm thấy ảnh phù hợp với caption: '{query}'")
            return None
        
        # Lấy image_key từ kết quả tìm kiếm đầu tiên
        image_key = results[0][1]
        print(f"Tìm thấy ảnh với key: {image_key}")
        
        # Lấy file ảnh từ MinIO - thời gian được đo trong hàm get_object
        image_path = storage.get_object("images", image_key)
        
        # Lưu kết quả vào cache
        if image_path:
            self._image_cache[query] = image_path
        
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