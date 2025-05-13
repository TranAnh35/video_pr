# Video PR

Chương trình xây dựng theo 3 container:
- **app**: Chạy FastAPI
- **minio**: Chạy MinIO
- **db**: Chạy PostgreSQL

## MinIO
Sẽ được sử dụng để lưu trữ object images.

## PostgreSQL
Database này sẽ lưu trữ thông tin về hình ảnh và vector embedding của caption. Sử dụng **PostgreSQL** kết hợp extension *pgvector* để lưu trữ và tìm kiếm vector.

### Schema cho images table
```sql
CREATE TABLE images (
    id SERIAL PRIMARY KEY,
    image_key VARCHAR(255) NOT NULL,
    width INT,
    height INT,
    format VARCHAR(32),
    size_bytes INT
);
```

### Schema cho captions table
```sql
CREATE TABLE captions (
    id SERIAL PRIMARY KEY,
    image_id INT NOT NULL,
    caption TEXT NOT NULL,
    caption_embedding VECTOR(512),
    FOREIGN KEY (image_id) REFERENCES images(id)
);
```

## Cách lưu trữ và tìm kiếm
**Lưu hình ảnh:**
1. Mỗi hình ảnh sẽ được hash để tránh trùng lặp (hash by image value). Giá trị sẽ lưu vào *image_key* trong **images table** và thay thành tên của ảnh trong *bucket* của **MinIO**.
2. Tạo embedding cho caption bằng model **all-MiniLM-L6-v2**.
3. Trích xuất những metadata của ảnh.
4. Lưu thông tin vào bảng images và captions. Nếu trường hợp ảnh trùng lặp, chỉ lưu thông tin vào captions. (Một bức ảnh có thể có nhiều caption khác nhau.)

**Tìm kiếm hình ảnh:** 
Sử dụng toán tử '<->' (L2 distance) để tìm kiếm hình ảnh có embedding gần nhất.

```sql
SELECT i.id, i.image_key
FROM images i
JOIN captions c ON i.id = c.image_id
ORDER BY c.caption_embedding <-> embedding_str::vector
LIMIT top_k
```

## Chạy local
Khởi tạo file .env dựa trên file .env.example

Và chạy chương trình với câu lệnh:
```
uvicorn app.web.application:app
```

## Build docker

- Do MinIO cần phải có tài khoản và phải cấu hình ACCESS_KEY và SECRET_KEY. Nên phải tự cấu hình container.
- Hiện tại đang lỗi thi khởi tạo PostgreSQL container trong docker-compose. Nên đang phải khởi tạo riêng

Khởi tạo file .env.docker từ .env.example và để thực hiện kết nối với db chính xác cần chinh sửa:
```
MINIO_HOST="name_minio_container"

POSTGRES_HOST="name_db_container"
```

Các container được kết nối thông qua network *video_pr_net*

Để chạy chương trình, hãy thực hiện các bước sau:

1. Tạo network video_pr_net:
```
docker network create video_pr_net
```

```
docker network connect video_pr_net <name_minio_container>
```

```
docker network connect video_pr_net <name_db_container>
```

2. Tạo và chạy các container:
```
docker-compose up --build
```