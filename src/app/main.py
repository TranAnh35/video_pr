import os
# Tắt các cảnh báo TensorFlow
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'  # 0=all, 1=info, 2=warning, 3=error
import tensorflow as tf
tf.get_logger().setLevel('ERROR')  # Chỉ hiển thị lỗi

from app.utils.connect import get_connector
from app.database.postgresql import get_db
from app.utils.timing import init_timing, set_logging
import matplotlib.pyplot as plt
from PIL import Image


class Application:
    def __init__(self):
        """Khởi tạo ứng dụng"""
        # Tắt log trùng lặp
        set_logging(False)
        
        # Khởi tạo hệ thống thống kê thời gian
        init_timing()
        
        # Khởi tạo các đối tượng cần thiết
        self.db = get_db()
        self.connector = get_connector()
        
    def initialize(self):
        """Khởi tạo các thành phần cần thiết"""
        # Khởi tạo cơ sở dữ liệu
        self.db.init_db()
        
    def run(self):
        """Chạy ứng dụng chính"""
        
        # Khởi tạo
        self.initialize()
        
        # Bắt đầu lấy ảnh
        print("\nBắt đầu lấy ảnh...")
        
        image_file_path = self.connector.get_image("A child playing on a rope net")
        
        if image_file_path:
            print(f"Image saved to: {image_file_path}")
        else:
            print("Could not retrieve image")
        
        # Hiển thị ảnh (đo riêng, không tính vào thời gian xử lý)
        if image_file_path and os.path.exists(image_file_path):
            # Hiển thị ảnh bằng matplotlib
            with Image.open(image_file_path) as image:
                plt.figure(figsize=(10, 8))
                plt.imshow(image)
                plt.axis('off')
                plt.tight_layout()
                plt.show()
                
            # Xóa file tạm
            try:
                os.unlink(image_file_path)
                print(f"Đã xóa file tạm: {image_file_path}")
            except Exception as e:
                print(f"Không thể xóa file tạm: {e}")


def main():
    """Entry point của ứng dụng"""
    # Khởi tạo ứng dụng
    app = Application()
    
    # Ghi lại thời gian khởi tạo
    app.run()


if __name__ == "__main__":
    main()