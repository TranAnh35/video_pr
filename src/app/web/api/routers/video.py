"""
Video processing related endpoints.
"""
import logging
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse, FileResponse
from pathlib import Path
import shutil
import tempfile
import os
from app.utils.video_processor import process_video

logger = logging.getLogger(__name__)
router = APIRouter()

# Thư mục lưu trữ 
UPLOAD_DIR = Path("uploads")
OUTPUT_DIR = Path("output")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Cấu hình
MAX_VIDEO_SIZE = 500 * 1024 * 1024  # 500MB cho video

@router.post("/process-video/", summary="Process a video file to detect scenes and extract frames")
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

        # Lưu file tạm thời
        temp_dir = tempfile.mkdtemp()
        try:
            video_path = Path(temp_dir) / file.filename
            with open(video_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            logger.info(f"Processing video file: {video_path}")
            success = process_video(str(video_path), str(OUTPUT_DIR), threshold=threshold)

            video_name = video_path.stem
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
            
        finally:
            # Dọn dẹp thư mục tạm
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception as e:
                logger.error(f"Error cleaning up temp directory: {str(e)}")
                
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error processing video {file.filename}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/frames/{video_name}/{frame_name}", summary="Get a frame image")
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
