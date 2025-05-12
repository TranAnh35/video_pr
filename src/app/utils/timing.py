import time

# Biến toàn cục để lưu trữ đối tượng thống kê thời gian
_global_time_stats = None
_disable_logging = False  # Tắt log để tránh in thông báo trùng lặp
_active_timers = {}  # Track active timers to handle parent-child relationships
_app_start_time = time.time()  # Thời gian bắt đầu chạy ứng dụng

class TimingStats:
    """Lớp lưu trữ thống kê thời gian thực hiện"""
    def __init__(self):
        self.timings = {}
        self.categories = {
            "database": [],    # Các hoạt động liên quan đến cơ sở dữ liệu
            "embedding": [],   # Các hoạt động liên quan đến embedding
            "storage": [],     # Các hoạt động liên quan đến lưu trữ
            "processing": [],  # Các hoạt động xử lý khác
            "display": []      # Hiển thị
        }
        self.category_totals = {cat: 0.0 for cat in self.categories}
        self.start_time = time.time()  # Thời điểm bắt đầu để tính thời gian tổng
        self.parent_child = {}  # Dictionary to track parent-child timing relationships
    
    def record(self, operation, duration, category="processing"):
        """Ghi lại thời gian thực hiện một hoạt động
        
        Args:
            operation (str): Tên hoạt động
            duration (float): Thời gian thực hiện (giây)
            category (str): Danh mục của hoạt động (database, embedding, storage, processing, display)
        """
        # Check for parent-child relationships to avoid double-counting
        has_parent = False
        for parent_op in _active_timers:
            if parent_op != operation:
                if parent_op not in self.parent_child:
                    self.parent_child[parent_op] = []
                if operation not in self.parent_child[parent_op]:
                    self.parent_child[parent_op].append(operation)
                has_parent = True
        
        # Record the timing regardless of parent-child relationship
        self.timings[operation] = duration
        
        # Only add to category totals if it doesn't have a parent (to avoid double-counting)
        if not has_parent:
            if category in self.categories:
                self.categories[category].append((operation, duration))
                self.category_totals[category] += duration
    
    def report(self):
        """In báo cáo thời gian thực hiện chi tiết"""
        print("\n" + "="*60)
        print("                   BÁO CÁO THỜI GIAN THỰC HIỆN")
        print("="*60)
        
        # Tính tổng thời gian thực tế từ thời điểm bắt đầu ứng dụng
        current_time = time.time()
        total_elapsed_from_init = current_time - self.start_time
        total_elapsed_from_start = current_time - _app_start_time
        
        # In báo cáo theo từng danh mục
        category_data = []
        total_root_operations = 0.0
        
        # Lọc các hoạt động gốc (không phải con của hoạt động khác)
        all_root_operations = {}  # Lưu các hoạt động gốc theo danh mục
        
        for category, operations in self.categories.items():
            if not operations:
                continue
                
            # Filter out operations that are children of other operations
            root_operations = []
            for op, dur in operations:
                is_child = False
                for parent, children in self.parent_child.items():
                    if op in children:
                        is_child = True
                        break
                if not is_child:
                    root_operations.append((op, dur))
            
            # Lưu các hoạt động gốc vào dictionary
            all_root_operations[category] = root_operations
            
            # Tính tổng thời gian của danh mục (chỉ từ các hoạt động gốc)
            category_time = sum(dur for _, dur in root_operations)
            category_data.append((category, category_time))
            total_root_operations += category_time
            
        # In báo cáo theo từng danh mục, nhưng bỏ qua hiển thị vì sẽ báo cáo riêng
        for category, operations in self.categories.items():
            if category == "display" or not operations:
                continue
                
            root_operations = all_root_operations.get(category, [])
            category_time = sum(dur for _, dur in root_operations)
            
            print(f"\n--- {category.upper()} ---")
            
            # Sắp xếp các hoạt động theo thời lượng giảm dần
            sorted_ops = sorted(operations, key=lambda x: x[1], reverse=True)
            
            # In chi tiết từng hoạt động
            for operation, duration in sorted_ops:
                # Đánh dấu các hoạt động con
                is_child = False
                for parent, children in self.parent_child.items():
                    if operation in children:
                        is_child = True
                        break
                
                prefix = "  ↳ " if is_child else ""
                print(f"{prefix}{operation:40}: {duration:.4f} giây")
            
            # In tổng thời gian của danh mục
            print(f"{f'Tổng thời gian {category}':40}: {category_time:.4f} giây")
        
        # Tính thời gian cho từng loại xử lý (không trùng lặp)
        embedding_time = sum(dur for _, dur in all_root_operations.get("embedding", []))
        database_time = sum(dur for _, dur in all_root_operations.get("database", []))
        storage_time = sum(dur for _, dur in all_root_operations.get("storage", []))
        other_time = sum(dur for _, dur in all_root_operations.get("processing", []))
        
        # In tổng kết thời gian xử lý (chỉ in một lần)
        print("\n" + "-"*60)
        print("TỔNG KẾT THỜI GIAN XỬ LÝ:")
        
        # Tránh chia cho 0
        if total_root_operations > 0:
            print(f"{'Tải và khởi tạo model embedding':40}: {embedding_time:.4f} giây ({embedding_time/total_root_operations*100:.1f}%)")
            print(f"{'Truy vấn và xử lý database':40}: {database_time:.4f} giây ({database_time/total_root_operations*100:.1f}%)")
            print(f"{'Đọc/ghi từ storage (MinIO)':40}: {storage_time:.4f} giây ({storage_time/total_root_operations*100:.1f}%)")
            print(f"{'Xử lý khác':40}: {other_time:.4f} giây ({other_time/total_root_operations*100:.1f}%)")
        else:
            print(f"{'Tải và khởi tạo model embedding':40}: {embedding_time:.4f} giây (0%)")
            print(f"{'Truy vấn và xử lý database':40}: {database_time:.4f} giây (0%)")
            print(f"{'Đọc/ghi từ storage (MinIO)':40}: {storage_time:.4f} giây (0%)")
            print(f"{'Xử lý khác':40}: {other_time:.4f} giây (0%)")
            
        print("-"*60)
        
        # Tính và hiển thị thời gian khởi động không được đo lường
        startup_time = total_elapsed_from_start - total_elapsed_from_init
        unmeasured_time = total_elapsed_from_init - total_root_operations
        
        # Báo cáo tổng thời gian
        print(f"{'TỔNG THỜI GIAN ĐÃ ĐO (Đã ghi nhận)':40}: {total_root_operations:.4f} giây")
        
        # Báo cáo thời gian hiển thị riêng nếu có
        display_operations = all_root_operations.get("display", [])
        if display_operations:
            display_time = sum(duration for _, duration in display_operations)
            print(f"{'Thời gian hiển thị (không tính vào xử lý)':40}: {display_time:.4f} giây")
        
        print("-"*60)
        # In thông tin về thời gian không được đo lường
        if unmeasured_time > 0:
            print(f"{'Thời gian khởi tạo ứng dụng (startup)':40}: {startup_time:.4f} giây")
            print(f"{'Thời gian không được đo lường trong xử lý':40}: {unmeasured_time:.4f} giây")
        
        total_with_display = total_root_operations
        if display_operations:
            total_with_display += display_time
            
        print(f"{'TỔNG THỜI GIAN TỪ KHỞI TẠO ĐẾN HẾT':40}: {total_elapsed_from_init:.4f} giây")
        print(f"{'TỔNG THỜI GIAN THỰC TẾ (cả startup)':40}: {total_elapsed_from_start:.4f} giây")
        print("="*60)


def init_timing():
    """Khởi tạo hệ thống thống kê thời gian toàn cục"""
    global _global_time_stats, _active_timers
    _global_time_stats = TimingStats()
    _active_timers = {}
    return _global_time_stats


def get_timing_stats():
    """Lấy đối tượng thống kê thời gian toàn cục"""
    global _global_time_stats
    if _global_time_stats is None:
        _global_time_stats = TimingStats()
    return _global_time_stats


def set_logging(enabled=True):
    """Bật/tắt việc in log thời gian"""
    global _disable_logging
    _disable_logging = not enabled


def start_timer(operation):
    """Bắt đầu đo thời gian cho một hoạt động
    
    Args:
        operation (str): Tên hoạt động
        
    Returns:
        float: Thời điểm bắt đầu
    """
    global _active_timers
    start = time.time()
    _active_timers[operation] = start
    return start


def stop_timer(operation, category="processing", print_log=False):
    """Dừng đo thời gian cho một hoạt động
    
    Args:
        operation (str): Tên hoạt động
        category (str): Danh mục của hoạt động
        print_log (bool): Có in log ra màn hình hay không
        
    Returns:
        float: Thời gian thực hiện (giây)
    """
    global _active_timers
    if operation in _active_timers:
        end = time.time()
        duration = end - _active_timers[operation]
        del _active_timers[operation]
        record_time(operation, duration, category, print_log)
        return duration
    return 0


def record_time(operation, duration, category="processing", print_log=False):
    """Ghi lại thời gian thực hiện một hoạt động vào thống kê toàn cục
    
    Args:
        operation (str): Tên hoạt động
        duration (float): Thời gian thực hiện (giây)
        category (str): Danh mục của hoạt động
        print_log (bool): Có in log ra màn hình hay không
    """
    stats = get_timing_stats()
    stats.record(operation, duration, category)
    
    global _disable_logging
    if print_log and not _disable_logging:
        print(f"{operation}: {duration:.4f} seconds")


def timed_function(category="processing"):
    """Decorator để đo thời gian thực hiện một hàm
    
    Args:
        category (str): Danh mục của hoạt động
        
    Returns:
        function: Decorator đo thời gian
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            operation = f"{func.__name__}"
            start_timer(operation)
            result = func(*args, **kwargs)
            stop_timer(operation, category)
            return result
        return wrapper
    return decorator


def report_timing():
    """In báo cáo thời gian thực hiện"""
    stats = get_timing_stats()
    stats.report() 