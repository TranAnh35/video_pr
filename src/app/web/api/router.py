import os
import logging
import tempfile
from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from fastapi.responses import JSONResponse, FileResponse
from typing import List, Optional
from app.utils.connect import upload_image_and_save_caption, get_image
from app.database.postgresql import search_image_by_caption, get_image_captions
from app.utils.video_processor import process_video
from pathlib import Path

logger = logging.getLogger(__name__)

router = APIRouter()

# Thư mục lưu trữ 
UPLOAD_DIR = Path("uploads")
OUTPUT_DIR = Path("output")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Cấu hình
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB cho hình ảnh
MAX_VIDEO_SIZE = 500 * 1024 * 1024  # 500MB cho video

# ---------- VIDEO API ENDPOINTS ----------

@router.post("/process-video/", summary="Process a video file to detect scenes and extract frames", tags=["VIDEO"])
async def process_video_endpoint(file: UploadFile = File(...), threshold: float = 0.3):
    """
    Upload and process a video file to detect scenes and extract first frames.

    Args:
        file: The video file to process (mp4, avi, mov, mkv).
        threshold (float): Scene detection threshold (0.0 - 1.0, default 0.3).

    Returns:
        JSON response with processing status and output details.
    """
    try:
        if not 0.0 <= threshold <= 1.0:
            logger.error(f"Invalid threshold value: {threshold}. Must be between 0.0 and 1.0.")
            raise HTTPException(status_code=400, detail="Threshold must be between 0.0 and 1.0")

        if file.size > MAX_VIDEO_SIZE:
            logger.error(f"File {file.filename} exceeds maximum size ({MAX_VIDEO_SIZE} bytes)")
            raise HTTPException(status_code=400, detail=f"File too large. Maximum size: {MAX_VIDEO_SIZE} bytes")

        allowed_extensions = {'.mp4', '.avi', '.mov', '.mkv'}
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in allowed_extensions:
            logger.error(f"Invalid file extension {file_ext} for file {file.filename}")
            raise HTTPException(status_code=400, detail=f"Invalid file extension. Allowed: {allowed_extensions}")

        video_path = UPLOAD_DIR / file.filename
        with open(video_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)

        logger.info(f"Uploaded video file: {video_path}")

        success = process_video(str(video_path), str(OUTPUT_DIR), threshold=threshold)

        video_name = Path(video_path).stem
        frame_output_dir = OUTPUT_DIR / video_name / "scene_frames"

        frames = []
        if frame_output_dir.exists():
            frames = [f"/api/frames/{video_name}/{f.name}" for f in frame_output_dir.iterdir() if f.suffix.lower() == '.jpg']

        response = {
            "status": "success" if success else "partial_success",
            "video_name": video_name,
            "frame_count": len(frames),
            "frames": frames
        }

        logger.info(f"Successfully processed video {video_name}. Generated {len(frames)} frames.")
        return JSONResponse(content=response)

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error processing video {file.filename}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    finally:
        if video_path.exists():
            try:
                video_path.unlink()
                logger.info(f"Deleted uploaded file: {video_path}")
            except Exception as e:
                logger.error(f"Error deleting uploaded file {video_path}: {str(e)}")

@router.get("/frames/{video_name}/{frame_name}", summary="Get a frame image", tags=["VIDEO"])
async def get_frame(video_name: str, frame_name: str):
    """
    Retrieve a frame image from the output directory.

    Args:
        video_name (str): Name of the video (without extension).
        frame_name (str): Name of the frame file (e.g., scene_001.jpg).

    Returns:
        FileResponse: The frame image file.
    """
    frame_path = OUTPUT_DIR / video_name / "scene_frames" / frame_name
    if not frame_path.exists():
        logger.error(f"Frame not found: {frame_path}")
        raise HTTPException(status_code=404, detail="Frame not found")
    return FileResponse(frame_path)

# ---------- IMAGE API ENDPOINTS ----------

@router.post("/images/upload/", summary="Upload an image with caption", tags=["IMAGE"])
async def upload_image(
    file: UploadFile = File(...),
    caption: str = Query(..., description="Caption for the image")
):
    """
    Upload an image file with caption and store in database
    
    Args:
        file: The image file to upload (jpg, jpeg, png)
        caption: Text description for the image
        
    Returns:
        JSON response with upload status and image details
    """
    try:
        # Kiểm tra kích thước file
        content = await file.read()
        if len(content) > MAX_IMAGE_SIZE:
            logger.error(f"File {file.filename} exceeds maximum size ({MAX_IMAGE_SIZE} bytes)")
            raise HTTPException(status_code=400, detail=f"File too large. Maximum size: {MAX_IMAGE_SIZE} bytes")
        
        # Kiểm tra định dạng file
        allowed_extensions = {'.jpg', '.jpeg', '.png', '.gif'}
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in allowed_extensions:
            logger.error(f"Invalid file extension {file_ext} for file {file.filename}")
            raise HTTPException(status_code=400, detail=f"Invalid file extension. Allowed: {allowed_extensions}")
        
        # Lưu file tạm thời
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=file_ext)
        temp_file.write(content)
        temp_file.close()
        
        try:
            # Upload hình ảnh và lưu caption
            result = upload_image_and_save_caption(temp_file.name, caption)
            
            if not result:
                raise HTTPException(status_code=500, detail="Failed to process image")
            
            # Kiểm tra nếu file này đã tồn tại
            is_duplicate = False
            if isinstance(result, str) and result.startswith("DUPLICATE:"):
                is_duplicate = True
                image_key = result.replace("DUPLICATE:", "")
                logger.info(f"Duplicate image detected, adding caption to existing image: {image_key}")
            else:
                image_key = result
            
            # Trả về response
            return JSONResponse(content={
                "status": "success",
                "message": "Image uploaded successfully",
                "image_key": image_key,
                "is_duplicate": is_duplicate,
                "caption": caption
            })
            
        finally:
            # Xóa file tạm
            try:
                os.unlink(temp_file.name)
            except Exception as e:
                logger.error(f"Error removing temp file: {str(e)}")
                
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error processing image upload: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/images/search/", summary="Search images by caption", tags=["IMAGE"])
async def search_images(
    query: str = Query(..., description="Search text to find related images"),
    limit: int = Query(5, description="Maximum number of results to return")
):
    """
    Search for images by caption text using semantic similarity
    
    Args:
        query: The text to search for
        limit: Maximum number of results to return (default: 5)
        
    Returns:
        JSON response with search results including image keys and preview URLs
    """
    try:
        # Tìm kiếm hình ảnh theo caption
        results = search_image_by_caption(query, top_k=limit)
        
        if not results:
            return JSONResponse(content={
                "status": "success",
                "message": "No matching images found",
                "results": []
            })
        
        # Tạo danh sách kết quả
        image_results = []
        for result in results:
            image_id, image_key = result
            
            # Lấy tất cả caption của hình ảnh
            captions = get_image_captions(image_key)
            caption_texts = [caption[1] for caption in captions]
            
            image_results.append({
                "image_key": image_key,
                "preview_url": f"/api/images/view/{image_key}",
                "captions": caption_texts
            })
        
        return JSONResponse(content={
            "status": "success",
            "message": f"Found {len(image_results)} matching images",
            "results": image_results
        })
        
    except Exception as e:
        logger.error(f"Error searching images: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/images/view/{image_key}", summary="View an image by its key", tags=["IMAGE"])
async def view_image(image_key: str):
    """
    Retrieve and view an image by its unique key
    
    Args:
        image_key: The unique key of the image
        
    Returns:
        The image file
    """
    try:
        # Sử dụng get_image để lấy đường dẫn đến file ảnh
        image_path = get_image(image_key)
        
        if not image_path or not os.path.exists(image_path):
            raise HTTPException(status_code=404, detail="Image not found")
        
        return FileResponse(image_path)
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error retrieving image: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# ---------- ADVANCED SEARCH API ENDPOINTS ----------

@router.get("/search/semantic/", summary="Semantic search for images based on query", tags=["ADVANCED SEARCH"])
async def semantic_search(
    query: str = Query(..., description="Text to search for"),
    limit: int = Query(10, description="Maximum number of results to return", ge=1, le=100)
):
    """
    Tìm kiếm ngữ nghĩa (semantic search) các hình ảnh dựa trên truy vấn văn bản
    
    Args:
        query: Chuỗi văn bản để tìm kiếm
        limit: Số lượng kết quả tối đa
    
    Returns:
        JSON response với các hình ảnh liên quan
    """
    try:
        # Thực hiện tìm kiếm ngữ nghĩa
        results = search_image_by_caption(query, top_k=limit)
        
        if not results:
            return JSONResponse(content={
                "status": "success",
                "message": "No matching images found",
                "count": 0,
                "results": []
            })
        
        # Chuẩn bị kết quả trả về
        formatted_results = []
        for result in results:
            image_id, image_key = result
            
            formatted_results.append({
                "image_key": image_key,
                "preview_url": f"/api/images/view/{image_key}",
                "details_url": f"/api/images/details/{image_key}"
            })
        
        return JSONResponse(content={
            "status": "success",
            "message": f"Found {len(formatted_results)} matching images",
            "count": len(formatted_results),
            "results": formatted_results
        })
        
    except Exception as e:
        logger.error(f"Error during semantic search: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/search/bulk/", summary="Bulk search for multiple queries", tags=["ADVANCED SEARCH"])
async def bulk_search(
    queries: List[str] = Query(..., description="List of search queries"),
    limit_per_query: int = Query(5, description="Maximum results per query", ge=1, le=20)
):
    """
    Thực hiện tìm kiếm hàng loạt với nhiều truy vấn
    
    Args:
        queries: Danh sách các chuỗi tìm kiếm
        limit_per_query: Số lượng kết quả tối đa cho mỗi truy vấn
    
    Returns:
        JSON response với kết quả từ mỗi truy vấn
    """
    try:
        results = {}
        
        for query in queries:
            # Tìm kiếm cho từng query
            search_results = search_image_by_caption(query, top_k=limit_per_query)
            
            # Định dạng kết quả
            formatted_results = []
            for result in search_results:
                image_id, image_key = result
                
                formatted_results.append({
                    "image_key": image_key,
                    "preview_url": f"/api/images/view/{image_key}",
                })
            
            # Lưu kết quả của truy vấn này
            results[query] = {
                "count": len(formatted_results),
                "results": formatted_results
            }
        
        return JSONResponse(content={
            "status": "success",
            "message": f"Completed bulk search for {len(queries)} queries",
            "results": results
        })
        
    except Exception as e:
        logger.error(f"Error during bulk search: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# ---------- API DOCUMENTATION ----------

@router.get("/endpoints/", summary="List all available API endpoints", tags=["API DOCUMENTATION"])
async def list_endpoints():
    """
    List all available API endpoints with descriptions
    
    Returns:
        JSON response with endpoint details
    """
    endpoints = [
        {
            "path": "/api/images/upload/",
            "method": "POST",
            "description": "Upload an image with caption"
        },
        {
            "path": "/api/images/search/",
            "method": "GET",
            "description": "Search images by caption"
        },
        {
            "path": "/api/images/view/{image_key}",
            "method": "GET",
            "description": "View an image by its key"
        },
        {
            "path": "/api/search/semantic/",
            "method": "GET",
            "description": "Semantic search for images"
        },
        {
            "path": "/api/search/bulk/",
            "method": "GET",
            "description": "Bulk search for multiple queries"
        },
        {
            "path": "/api/process-video/",
            "method": "POST",
            "description": "Process a video to detect scenes and extract frames"
        },
        {
            "path": "/api/frames/{video_name}/{frame_name}",
            "method": "GET",
            "description": "Get a frame image from processed video"
        }
    ]
    
    return JSONResponse(content={
        "status": "success",
        "endpoints": endpoints
    })