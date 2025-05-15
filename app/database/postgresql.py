import psycopg2
from app.models.embedding import encode_text, vector_to_pg_format
from app.config.settings import settings
import logging

logger = logging.getLogger(__name__)

class PostgresDB:
    _instance = None  # Singleton pattern
    
    @classmethod
    def get_instance(cls):
        """Singleton pattern to return a single instance of database"""
        if cls._instance is None:
            cls._instance = PostgresDB()
        return cls._instance
    
    def __init__(self):
        """Initialize the database connection"""
        if PostgresDB._instance is not None:
            return
            
        self.conn = None
        self.cursor = None
        self._search_cache = {}
        
        try:
            self.conn = psycopg2.connect(
                dbname=settings.POSTGRES_DB,
                user=settings.POSTGRES_USER, 
                password=settings.POSTGRES_PASSWORD, 
                host=settings.POSTGRES_HOST,
                port=settings.POSTGRES_PORT
            )
            self.cursor = self.conn.cursor()
            logger.info("PostgreSQL connection established")
        except Exception as e:
            logger.error(f"PostgreSQL connection error: {e}")
            print("Continuing without database connection...")
    
    def is_connected(self):
        """Check if the database connection is available"""
        return self.conn is not None and self.cursor is not None
    
    def init_db(self):
        """Initialize the database structure if it doesn't exist"""
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
        """Save image and caption information into the database"""
        logger.info(f"Saving image: key={image_key}, caption='{caption}'")
        self._search_cache.clear()
        
        if not self.is_connected():
            logger.error("No database connection available. Can't save image data.")
            return False
        
        # Check if caption already exists
        if self.check_caption_exists(caption):
            logger.info(f"Caption '{caption}' already exists in the database. Skipping save.")
            return False
        
        self.conn.rollback()
            
        try:
            self.cursor.execute(
                "SELECT id FROM images WHERE image_key = %s",
                (image_key,)
            )
            image_result = self.cursor.fetchone()
            
            # If the image does not exist, add it
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
            
            # Add new caption for the image
            if with_embeding:
                embedding = encode_text(caption)
                
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
            
            logger.info(f"Image saved successfully with key: {image_key}")
            return True
        except Exception as e:
            if self.conn:
                self.conn.rollback()
            logger.error(f"Error saving image: {e}")
            return False

    def get_image_captions(self, image_key):
        """Get all captions for a specific image"""
        logger.debug(f"Getting captions for image: key={image_key}")
        if not self.is_connected():
            logger.error("No database connection available. Can't get image captions.")
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
            logger.error(f"Error getting captions: {e}")
            return []
    
    def search_image_by_caption(self, caption, top_k=1, exclude_image_keys=None):
        """Search images based on caption"""        
        logger.info(f"Searching images by caption: '{caption}' (top_k={top_k}, exclude={exclude_image_keys})")
        # Check cache
        cache_key = f"{caption}:{top_k}:{exclude_image_keys}"
        if cache_key in self._search_cache:
            result = self._search_cache[cache_key]
            logger.debug(f"Cache hit: Using search results from cache for caption: '{caption}'")
            return result
        
        if not self.is_connected():
            logger.error("No database connection available. Can't search images.")
            return []
        
        self.conn.rollback()
    
        try:
            embedding = encode_text(caption)
            
            embedding_str = vector_to_pg_format(embedding)
            
            import time

            start_time = time.time()

            if exclude_image_keys and len(exclude_image_keys) > 0:
                placeholders = ', '.join(['%s'] * len(exclude_image_keys))
                self.cursor.execute(
                    f"""
                    SELECT i.id, i.image_key
                    FROM images i
                    JOIN captions c ON i.id = c.image_id
                    WHERE i.image_key NOT IN ({placeholders})
                    GROUP BY i.id, i.image_key
                    ORDER BY MIN(c.caption_embedding <-> %s::vector)
                    LIMIT %s
                    """,
                    (*exclude_image_keys, embedding_str, top_k)
                )
            else:
                self.cursor.execute(
                    """
                    SELECT i.id, i.image_key
                    FROM images i
                    JOIN captions c ON i.id = c.image_id
                    GROUP BY i.id, i.image_key
                    ORDER BY MIN(c.caption_embedding <-> %s::vector)
                    LIMIT %s
                    """,
                    (embedding_str, top_k)
                )

            
            results = self.cursor.fetchall()
            end_time = time.time()

            logger.info(f"Search results: {results}")
            logger.info(f"Time to search in database: {end_time - start_time:.6f} seconds")

            if not results:
                logger.info("No matching images found.")
                return []
            
            # Save results to cache
            self._search_cache[cache_key] = results
                
            return results
        except Exception as e:
            if self.conn:
                self.conn.rollback()
            logger.error(f"Error searching images: {e}")
            return []
    
    def check_image_exists(self, image_key):
        """Check if the image exists in the database"""
        logger.debug(f"Checking if image exists: key={image_key}")
        if not self.is_connected():
            logger.error("No database connection available. Can't check image existence.")
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
            logger.error(f"Error checking image existence: {e}")
            return False
    
    def check_caption_exists(self, caption):
        """Check if the caption already exists for any image in the database"""
        logger.debug(f"Checking if caption exists: '{caption}'")
        if not self.is_connected():
            logger.error("No database connection available. Can't check caption existence.")
            return False
        
        self.conn.rollback()
        
        try:
            self.cursor.execute(
                "SELECT 1 FROM captions WHERE caption = %s LIMIT 1",
                (caption,)
            )
            
            return self.cursor.fetchone() is not None
        except Exception as e:
            if self.conn:
                self.conn.rollback()
            logger.error(f"Error checking caption existence: {e}")
            return False
    
    def add_caption_to_image(self, image_key, caption, with_embeding=True):
        """Add new caption to an existing image"""
        logger.info(f"Adding caption to image: key={image_key}, caption='{caption}'")
        if not self.is_connected():
            logger.error("No database connection available. Can't add caption.")
            return False
        
        # Check if caption already exists in any image
        if self.check_caption_exists(caption):
            logger.info(f"Caption '{caption}' already exists in the database. Skipping addition.")
            return False
        
        self.conn.rollback()
        
        try:
            self.cursor.execute(
                "SELECT id FROM images WHERE image_key = %s",
                (image_key,)
            )
            
            result = self.cursor.fetchone()
            if not result:
                logger.info(f"Image not found with key: {image_key}")
                return False
                
            image_id = result[0]
            
            if with_embeding:
                embedding = encode_text(caption)
                
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
            logger.info(f"Caption added successfully for image with key: {image_key}")
            return True
            
        except Exception as e:
            if self.conn:
                self.conn.rollback()
            logger.error(f"Error adding caption: {e}")
            return False

    def __del__(self):
        """Destroy the object and close the connection"""
        try:
            if self.cursor:
                self.cursor.close()
            if self.conn:
                self.conn.close()
            logger.info("PostgreSQL connection closed")
        except Exception as e:
            logger.error(f"Error closing PostgreSQL connection: {e}")


# Singleton instance
_db_instance = None

def get_db():
    """Get database instance"""
    global _db_instance
    if _db_instance is None:
        _db_instance = PostgresDB.get_instance()
    return _db_instance