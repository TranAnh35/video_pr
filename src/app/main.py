import os
# Tắt các cảnh báo TensorFlow
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'  # 0=all, 1=info, 2=warning, 3=error
import tensorflow as tf
tf.get_logger().setLevel('ERROR')  # Chỉ hiển thị lỗi

from app.utils.connect import get_connector
from app.database.postgresql import get_db
from app.config.logging_setup import setup_logging
import matplotlib.pyplot as plt
from PIL import Image


class Application:
    def __init__(self):
        """Khởi tạo ứng dụng"""
        setup_logging()

        self.db = get_db()
        self.connector = get_connector()
        
    def initialize(self):
        """Khởi tạo các thành phần cần thiết"""
        self.db.init_db()
        
    def run(self):
        """Chạy ứng dụng chính"""

        self.initialize()
        
        print("\nBắt đầu lấy ảnh...")
        
        image_file_path = self.connector.get_image("A child playing on a rope net")
        
        if image_file_path:
            print(f"Image saved to: {image_file_path}")
        else:
            print("Could not retrieve image")
        
        if image_file_path and os.path.exists(image_file_path):
            with Image.open(image_file_path) as image:
                plt.figure(figsize=(10, 8))
                plt.imshow(image)
                plt.axis('off')
                plt.tight_layout()
                plt.show()
                
            try:
                os.unlink(image_file_path)
                print(f"Đã xóa file tạm: {image_file_path}")
            except Exception as e:
                print(f"Không thể xóa file tạm: {e}")


if __name__ == "__main__":
    app = Application()
    app.run()