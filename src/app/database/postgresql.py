import psycopg2
from psycopg2.extras import RealDictCursor
from app.models.embedding import encode_text, vector_to_pg_format
from app.config.setting import DB_CONFIG
import logging

logger = logging.getLogger(__name__)

class PostgresDB:
    _instance = None  # Singleton pattern
    
    @classmethod
    def get_instance(cls):
        """Singleton pattern để trả về instance duy nhất của database"""
        if cls._instance is None:
            cls._instance = PostgresDB()
        return cls._instance
    
    def __init__(self):
        """Khởi tạo kết nối database"""
        if PostgresDB._instance is not None:
            # Nếu đã có instance, không tạo mới
            return
            
        self.conn = None
        self.cursor = None
        self._search_cache = {}  # Cache cho kết quả tìm kiếm
        
        try:
            self.conn = psycopg2.connect(
                dbname=DB_CONFIG["database"],
                user=DB_CONFIG["user"], 
                password=DB_CONFIG["password"], 
                host=DB_CONFIG["host"],
                port=DB_CONFIG["port"]
            )
            self.cursor = self.conn.cursor()
            logger.info("PostgreSQL connection established")
        except Exception as e:
            logger.error(f"PostgreSQL connection error: {e}")
            print("Continuing without database connection...")
    
    def is_connected(self):
        """Kiểm tra kết nối có khả dụng không"""
        return self.conn is not None and self.cursor is not None
    
    def init_db(self):
        """Khởi tạo cấu trúc database nếu chưa tồn tại"""
        if not self.is_connected():
            print("No database connection available. Can't initialize database.")
            return
            
        self.conn.rollback()
            
        try:
            has_vector = False
            try:
                self.cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
                self.conn.commit()
                has_vector = True
                logger.info("pgvector extension available")
            except Exception as e:
                self.conn.rollback()
                logger.error(f"pgvector extension not available: {e}")
                print("Will create tables without vector support")
            
            if has_vector:
                # Tạo bảng images chỉ lưu thông tin về image
                self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS images (
                    id SERIAL PRIMARY KEY,
                    image_key VARCHAR(255) NOT NULL UNIQUE,
                    width INT,
                    height INT,
                    format VARCHAR(32),
                    size_bytes INT
                )
                """)
                logger.info("Created images table")
                
                # Tạo bảng captions để lưu nhiều caption cho mỗi image
                self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS captions (
                    id SERIAL PRIMARY KEY,
                    image_id INT NOT NULL,
                    caption TEXT NOT NULL,
                    caption_embedding VECTOR(384),
                    FOREIGN KEY (image_id) REFERENCES images (id) ON DELETE CASCADE
                )
                """)
                logger.info("Created captions table with vector support")
            else:
                self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS images (
                    id SERIAL PRIMARY KEY,
                    image_key VARCHAR(255) NOT NULL UNIQUE,
                    width INT,
                    height INT,
                    format VARCHAR(32),
                    size_bytes INT
                )
                """)
                logger.info("Created images table without vector support")
                
                self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS captions (
                    id SERIAL PRIMARY KEY,
                    image_id INT NOT NULL,
                    caption TEXT NOT NULL,
                    FOREIGN KEY (image_id) REFERENCES images (id) ON DELETE CASCADE
                )
                """)
                logger.info("Created captions table without vector support")
            
            self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS prompts (
                id SERIAL PRIMARY KEY,
                user_id INT,
                prompt_text TEXT NOT NULL
            )
            """)
            
            self.conn.commit()
            
            logger.info("Database initialized successfully")
        except Exception as e:
            if self.conn:
                self.conn.rollback()
            logger.error(f"Error initializing database: {e}")
    
    def save_image(self, image_key, image_metadata, caption, with_embeding=True):
        """Lưu thông tin hình ảnh và caption vào database"""
        logger.info(f"Saving image: key={image_key}, caption='{caption}'")
        # Clear cache khi có một hình ảnh hoặc caption mới được lưu
        self._search_cache.clear()
        
        if not self.is_connected():
            print("No database connection available. Can't save image data.")
            return False
        
        self.conn.rollback()
            
        try:
            # Kiểm tra xem image đã tồn tại chưa
            self.cursor.execute(
                "SELECT id FROM images WHERE image_key = %s",
                (image_key,)
            )
            image_result = self.cursor.fetchone()
            
            # Nếu image chưa tồn tại, thêm mới
            if not image_result:
                self.cursor.execute(
                    "INSERT INTO images (image_key, width, height, format, size_bytes) VALUES (%s, %s, %s, %s, %s) RETURNING id",
                    (
                        image_key,
                        image_metadata['width'],
                        image_metadata['height'],
                        image_metadata['format'],
                        image_metadata['size_bytes']
                    )
                )
                image_id = self.cursor.fetchone()[0]
            else:
                image_id = image_result[0]
            
            # Thêm caption mới cho image
            if with_embeding:
                # Tạo embedding vector từ caption
                embedding = encode_text(caption)
                
                # Chuyển embedding thành chuỗi định dạng PostgreSQL VECTOR
                embedding_str = vector_to_pg_format(embedding)
                
                self.cursor.execute(
                    "INSERT INTO captions (image_id, caption, caption_embedding) VALUES (%s, %s, %s::vector)",
                    (image_id, caption, embedding_str)
                )
            else:
                self.cursor.execute(
                    "INSERT INTO captions (image_id, caption) VALUES (%s, %s)",
                    (image_id, caption)
                )
                
            self.conn.commit()
            
            logger.info(f"Đã lưu hình ảnh với key: {image_key}")
            return True
        except Exception as e:
            if self.conn:
                self.conn.rollback()
            logger.error(f"Lỗi khi lưu hình ảnh: {e}")
            return False

    def get_image_captions(self, image_key):
        """Lấy tất cả caption của một hình ảnh"""
        logger.debug(f"Getting captions for image: key={image_key}")
        if not self.is_connected():
            print("No database connection available. Can't get image captions.")
            return []
        
        self.conn.rollback()
        
        try:
            self.cursor.execute(
                """
                SELECT c.id, c.caption
                FROM captions c
                JOIN images i ON c.image_id = i.id
                WHERE i.image_key = %s
                """,
                (image_key,)
            )
            
            return self.cursor.fetchall()
        except Exception as e:
            if self.conn:
                self.conn.rollback()
            logger.error(f"Lỗi khi lấy caption: {e}")
            return []
    
    def search_image_by_caption(self, caption, top_k=1):
        """Tìm kiếm hình ảnh dựa trên caption"""        
        logger.info(f"Searching images by caption: '{caption}' (top_k={top_k})")
        # Kiểm tra cache
        cache_key = f"{caption}:{top_k}"
        if cache_key in self._search_cache:
            result = self._search_cache[cache_key]
            logger.debug(f"Cache hit: Sử dụng kết quả tìm kiếm từ cache cho caption: '{caption}'")
            return result
        
        if not self.is_connected():
            print("No database connection available. Can't search images.")
            return []
        
        self.conn.rollback()
    
        try:
            # Tạo embedding vector từ caption
            embedding = encode_text(caption)
            
            # Chuyển embedding thành chuỗi định dạng PostgreSQL VECTOR
            embedding_str = vector_to_pg_format(embedding)
            
            import time

            start_time = time.time()

            # Truy vấn tìm kiếm hình ảnh dựa trên độ tương đồng với vector embedding
            self.cursor.execute(
                """
                SELECT i.id, i.image_key
                FROM images i
                JOIN captions c ON i.id = c.image_id
                ORDER BY c.caption_embedding <-> %s::vector
                LIMIT %s
                """,
                (embedding_str, top_k)
            )

            
            results = self.cursor.fetchall()
            end_time = time.time()

            logger.info(f"Thời gian tìm kiếm trong database: {end_time - start_time:.6f} giây")

            if not results:
                logger.info("Không tìm thấy hình ảnh phù hợp.")
                return []
            
            # Lưu kết quả vào cache
            self._search_cache[cache_key] = results
                
            return results
        except Exception as e:
            if self.conn:
                self.conn.rollback()
            logger.error(f"Lỗi khi tìm kiếm hình ảnh: {e}")
            return []
    
    def check_image_exists(self, image_key):
        """Kiểm tra xem hình ảnh đã tồn tại trong database chưa"""
        logger.debug(f"Checking if image exists: key={image_key}")
        if not self.is_connected():
            print("No database connection available. Can't check image existence.")
            return False
        
        self.conn.rollback()
        
        try:
            self.cursor.execute(
                "SELECT 1 FROM images WHERE image_key = %s",
                (image_key,)
            )
            
            return self.cursor.fetchone() is not None
        except Exception as e:
            if self.conn:
                self.conn.rollback()
            logger.error(f"Lỗi khi kiểm tra sự tồn tại của hình ảnh: {e}")
            return False
    
    def add_caption_to_image(self, image_key, caption, with_embeding=True):
        """Thêm caption mới cho hình ảnh đã tồn tại"""
        logger.info(f"Adding caption to image: key={image_key}, caption='{caption}'")
        if not self.is_connected():
            print("No database connection available. Can't add caption.")
            return False
        
        self.conn.rollback()
        
        try:
            # Lấy image_id từ image_key
            self.cursor.execute(
                "SELECT id FROM images WHERE image_key = %s",
                (image_key,)
            )
            
            result = self.cursor.fetchone()
            if not result:
                print(f"Không tìm thấy hình ảnh với key: {image_key}")
                return False
                
            image_id = result[0]
            
            # Kiểm tra xem caption đã tồn tại cho hình ảnh này chưa
            self.cursor.execute(
                "SELECT 1 FROM captions WHERE image_id = %s AND caption = %s",
                (image_id, caption)
            )
            
            if self.cursor.fetchone():
                print(f"Caption này đã tồn tại cho hình ảnh với key: {image_key}")
                return True
                
            # Thêm caption mới
            if with_embeding:
                # Tạo embedding vector từ caption
                embedding = encode_text(caption)
                
                # Chuyển embedding thành chuỗi định dạng PostgreSQL VECTOR
                embedding_str = vector_to_pg_format(embedding)
                
                self.cursor.execute(
                    "INSERT INTO captions (image_id, caption, caption_embedding) VALUES (%s, %s, %s::vector)",
                    (image_id, caption, embedding_str)
                )
            else:
                self.cursor.execute(
                    "INSERT INTO captions (image_id, caption) VALUES (%s, %s)",
                    (image_id, caption)
                )
                
            self.conn.commit()
            print(f"Đã thêm caption mới cho hình ảnh với key: {image_key}")
            return True
            
        except Exception as e:
            if self.conn:
                self.conn.rollback()
            print(f"Lỗi khi thêm caption: {e}")
            return False

    def __del__(self):
        """Hủy đối tượng, đóng kết nối"""
        try:
            if self.cursor:
                self.cursor.close()
            if self.conn:
                self.conn.close()
            print("PostgreSQL connection closed")
        except Exception as e:
            print(f"Error closing PostgreSQL connection: {e}")


# ---------- Compatibility functions for existing code ----------

# Singleton instance
_db_instance = None

def get_db():
    """Get database instance"""
    global _db_instance
    if _db_instance is None:
        _db_instance = PostgresDB.get_instance()
    return _db_instance

def init_db():
    """Initialize database (compatibility function)"""
    get_db().init_db()

def save_image(image_key, metadata, caption, with_embeding=True):
    """Save image (compatibility function)"""
    return get_db().save_image(image_key, metadata, caption, with_embeding=with_embeding)

def search_image_by_caption(caption, top_k=1):
    """Search image by caption (compatibility function)"""
    return get_db().search_image_by_caption(caption, top_k)

def get_image_captions(image_key):
    """Get all captions for an image (compatibility function)"""
    return get_db().get_image_captions(image_key)

def check_image_exists(image_key):
    """Check if an image exists in the database (compatibility function)"""
    return get_db().check_image_exists(image_key)

def add_caption_to_image(image_key, caption, with_embeding=True):
    """Add a new caption to an existing image (compatibility function)"""
    return get_db().add_caption_to_image(image_key, caption, with_embeding)