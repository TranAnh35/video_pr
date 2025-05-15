"""
Image management related endpoints.
"""
import logging
from fastapi import APIRouter, HTTPException, Query, UploadFile, File
from fastapi.responses import JSONResponse
from typing import List, Optional
import tempfile
import os
import hashlib
from app.database.postgresql import get_db
from app.utils.connect import get_connector
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()

class ImageResponse(BaseModel):
    id: int
    image_key: str
    width: Optional[int] = None
    height: Optional[int] = None
    format: Optional[str] = None
    size_bytes: Optional[int] = None

@router.get("/detail/{image_key}", response_model=ImageResponse, summary="Get image details")
async def get_image_details(image_key: str):
    """
    Get detailed information about a specific image
    
    Args:
        image_key: The unique key of the image
        
    Returns:
        Image details including metadata
    """
    try:
        db = get_db()
        cursor = db.cursor
        cursor.execute(
            """
            SELECT id, image_key, width, height, format, size_bytes
            FROM images
            WHERE image_key = %s
            """,
            (image_key,)
        )
        result = cursor.fetchone()
        
        if not result:
            raise HTTPException(status_code=404, detail="Image not found")
        
        # Convert to dict with column names as keys
        columns = [desc[0] for desc in cursor.description]
        image_data = dict(zip(columns, result))
        
        return JSONResponse(content={
            "status": "success",
            "data": image_data
        })
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error getting image details: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/list/", summary="List all images with pagination")
async def list_images(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of records to return")
):
    """
    Get a paginated list of all images
    
    Args:
        skip: Number of records to skip (for pagination)
        limit: Maximum number of records to return (max 100)
        
    Returns:
        Paginated list of images with their details
    """
    try:
        db = get_db()
        cursor = db.cursor
        cursor.execute("SELECT COUNT(*) FROM images")
        total = cursor.fetchone()[0]
        
        cursor.execute(
            """
            SELECT id, image_key, width, height, format, size_bytes
            FROM images
            LIMIT %s OFFSET %s
            """,
            (limit, skip)
        )
        
        # Convert results to list of dicts
        columns = [desc[0] for desc in cursor.description]
        images = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        return JSONResponse(content={
            "status": "success",
            "data": {
                "total": total,
                "skip": skip,
                "limit": limit,
                "images": images
            }
        })
        
    except Exception as e:
        logger.error(f"Error listing images: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/check-exists/", summary="Check if an image already exists in the dataset")
async def check_image_exists(
    file: UploadFile = File(...),
):
    """
    Check if an uploaded image already exists in the dataset
    
    Args:
        file: The image file to check
        
    Returns:
        JSON response with existence status and image details if found
    """
    try:
        content = await file.read()
        
        # Create a temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1])
        temp_file.write(content)
        temp_file.close()
        
        try:
            # Calculate hash of the file
            sha256_hash = hashlib.sha256()
            with open(temp_file.name, "rb") as f:
                for byte_block in iter(lambda: f.read(65536), b""):
                    sha256_hash.update(byte_block)
            content_hash = sha256_hash.hexdigest()
            
            # Determine file extension
            file_ext = os.path.splitext(file.filename)[1]
            if not file_ext:
                file_ext = ".jpg"  # Default if no extension provided
            
            # Create unique key in same format as storage system
            unique_key = f"{content_hash}{file_ext}"
            
            # Check if image exists in database
            db = get_db()
            exists = db.check_image_exists(unique_key)
            
            if exists:
                # Get additional image information
                cursor = db.cursor
                cursor.execute(
                    """
                    SELECT id, image_key, width, height, format, size_bytes
                    FROM images
                    WHERE image_key = %s
                    """,
                    (unique_key,)
                )
                result = cursor.fetchone()
                
                # Convert to dict with column names as keys
                columns = [desc[0] for desc in cursor.description]
                image_data = dict(zip(columns, result))
                
                # Get the image captions as well
                captions = db.get_image_captions(unique_key)
                caption_list = [caption[1] for caption in captions]
                
                return JSONResponse(content={
                    "status": "success",
                    "exists": True,
                    "message": "Image already exists in dataset",
                    "image_data": image_data,
                    "captions": caption_list
                })
            else:
                return JSONResponse(content={
                    "status": "success",
                    "exists": False,
                    "message": "Image does not exist in dataset",
                    "calculated_key": unique_key
                })
        finally:
            # Clean up the temporary file
            try:
                os.unlink(temp_file.name)
            except Exception as e:
                logger.error(f"Error removing temp file: {str(e)}")
                
    except Exception as e:
        logger.error(f"Error checking image existence: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
