"""
Image management related endpoints.
"""
import logging
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import List, Optional
from app.database.postgresql import get_db
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
