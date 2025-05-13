from app.database.minio import MinioStorage, get_storage
from app.database.postgresql import PostgresDB
from app.utils.connect import get_connector

import os
import logging
import argparse

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("setup_db")

def setup_database():
    """Khởi tạo kết nối database và tạo cấu trúc bảng"""
    logger.info("Đang khởi tạo database...")
    
    PostgresDB.get_instance().init_db()
    
    minio = get_storage()
    if not minio.is_connected():
        logger.error("Không thể kết nối đến MinIO server!")
        return False
    
    logger.info("Đã khởi tạo kết nối database thành công")
    logger.info("Hệ thống đã được cấu hình để sử dụng content-based hashing để tránh trùng lặp file")
    logger.info("Các file giống nhau về nội dung sẽ được phát hiện, ngay cả khi được tải lên từ các nguồn khác nhau")
    return True

def load_images_and_captions(caption_file, images_folder, limit=None):
    """
    Tải hình ảnh và caption lên database
    
    Args:
        caption_file: Đường dẫn đến file chứa các cặp image,caption
        images_folder: Thư mục chứa các file hình ảnh
        limit: Số lượng hình ảnh tối đa cần tải (None = tất cả)
    """
    logger.info(f"Bắt đầu tải hình ảnh từ {images_folder}")
    
    if not os.path.exists(images_folder):
        logger.error(f"Thư mục hình ảnh không tồn tại: {images_folder}")
        return
    
    if not os.path.exists(caption_file):
        logger.error(f"File caption không tồn tại: {caption_file}")
        return
    
    with open(caption_file, 'r', encoding='utf-8') as file:
        processed = 0
        success = 0
        failure = 0
        skipped = 0
        duplicated = 0
        
        for line in file:
            if limit is not None and processed >= limit:
                break
                
            try:
                content = line.strip()
                if not content or ',' not in content:
                    skipped += 1
                    continue
                    
                parts = content.split(',', 1)
                if len(parts) != 2:
                    logger.warning(f"Định dạng không hợp lệ: {content}")
                    skipped += 1
                    continue
                    
                image_name, caption = parts
                image_path = os.path.join(images_folder, image_name)
                
                if not os.path.exists(image_path):
                    logger.warning(f"File không tồn tại: {image_path}")
                    failure += 1
                    continue
                
                if processed > 0 and processed % 10 == 0:
                    logger.info(f"Đang xử lý hình ảnh {processed}/{limit if limit else 'tất cả'}...")
                
                result = get_connector().upload_image_and_save_caption(image_path, caption)
                
                if result:
                    if result.startswith("DUPLICATE:"):
                        duplicated += 1
                        logger.debug(f"Phát hiện trùng lặp: {image_name}")
                    else:
                        success += 1
                else:
                    failure += 1
                    
                processed += 1
                
                if processed % 10 == 0:
                    logger.info(f"Đã xử lý {processed} hình ảnh " +
                               f"(thành công: {success}, trùng lặp: {duplicated}, " +
                               f"thất bại: {failure}, bỏ qua: {skipped})")
                    
            except Exception as e:
                logger.error(f"Lỗi khi xử lý dòng {processed + 1}: {str(e)}")
                failure += 1
                processed += 1
    
    logger.info(f"Hoàn thành! Tổng số: {processed} hình ảnh " +
               f"(thành công: {success}, trùng lặp: {duplicated}, " +
               f"thất bại: {failure}, bỏ qua: {skipped})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Thiết lập dữ liệu hình ảnh và caption')
    parser.add_argument('--caption', type=str, default='resource/captions.txt',
                       help='Đường dẫn đến file caption (default: resource/captions.txt)')
    parser.add_argument('--images', type=str, default='resource/Images',
                       help='Đường dẫn đến thư mục hình ảnh (default: resource/Images)')
    parser.add_argument('--limit', type=int, default=10,
                       help='Số lượng hình ảnh tối đa cần tải (default: 10, 0 = tất cả)')
    parser.add_argument('--init-only', action='store_true',
                       help='Chỉ khởi tạo database, không tải hình ảnh')
    parser.add_argument('--upload-only', action='store_true',
                       help='Chỉ tải hình ảnh lên, không khởi tạo lại database')
    
    args = parser.parse_args()
    
    limit = None if args.limit == 0 else args.limit
    
    if args.upload_only:
        logger.info("Chế độ chỉ tải ảnh - Bỏ qua bước khởi tạo database")
        load_images_and_captions(args.caption, args.images, limit=limit)
    else:
        if setup_database():
            if not args.init_only:
                load_images_and_captions(args.caption, args.images, limit=limit)
        else:
            logger.error("Không thể tiếp tục do lỗi khởi tạo database")