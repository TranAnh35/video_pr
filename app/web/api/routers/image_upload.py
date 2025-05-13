import logging
import tempfile
import os
from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from fastapi.responses import JSONResponse, FileResponse
from pathlib import Path
from app.utils.connect import get_connector

logger = logging.getLogger(__name__)
router = APIRouter()

MAX_IMAGE_SIZE = 10 * 1024 * 1024

@router.post("/upload/", summary="Upload an image with caption")
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
        content = await file.read()
        if len(content) > MAX_IMAGE_SIZE:
            logger.error(f"File {file.filename} exceeds maximum size ({MAX_IMAGE_SIZE} bytes)")
            raise HTTPException(status_code=400, detail=f"File too large. Maximum size: {MAX_IMAGE_SIZE} bytes")
        
        allowed_extensions = {'.jpg', '.jpeg', '.png'}
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in allowed_extensions:
            logger.error(f"Invalid file extension {file_ext} for file {file.filename}")
            raise HTTPException(status_code=400, detail=f"Invalid file extension. Allowed: {allowed_extensions}")
        
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=file_ext)
        temp_file.write(content)
        temp_file.close()
        
        try:
            result = get_connector().upload_image_and_save_caption(temp_file.name, caption)
            
            if not result:
                raise HTTPException(status_code=500, detail="Failed to process image")
            
            is_duplicate = False
            if isinstance(result, str) and result.startswith("DUPLICATE:"):
                is_duplicate = True
                image_key = result.replace("DUPLICATE:", "")
                logger.info(f"Duplicate image detected, adding caption to existing image: {image_key}")
            else:
                image_key = result
            
            return JSONResponse(content={
                "status": "success",
                "message": "Image uploaded successfully",
                "image_key": image_key,
                "is_duplicate": is_duplicate,
                "caption": caption
            })
            
        finally:
            try:
                os.unlink(temp_file.name)
            except Exception as e:
                logger.error(f"Error removing temp file: {str(e)}")
                
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error processing image upload: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/view/{image_key}", summary="View an image by its key")
async def view_image(image_key: str):
    """
    Retrieve and view an image by its unique key
    
    Args:
        image_key: The unique key of the image
        
    Returns:
        The image file
    """
    try:
        image_path = get_connector().get_image(image_key)
        
        if not image_path or not os.path.exists(image_path):
            raise HTTPException(status_code=404, detail="Image not found")
        
        return FileResponse(image_path)
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error retrieving image: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
