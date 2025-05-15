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
            duplicate_type = None
            image_key = result
            
            if isinstance(result, str):
                if result.startswith("DUPLICATE_IMAGE:"):
                    is_duplicate = True
                    duplicate_type = "image"
                    image_key = result.replace("DUPLICATE_IMAGE:", "")
                    logger.info(f"Duplicate image detected: {image_key}")
                elif result.startswith("DUPLICATE_CAPTION:"):
                    is_duplicate = True
                    duplicate_type = "caption"
                    image_key = None  # We don't have an image key for caption duplicates
                    logger.info(f"Duplicate caption detected: {caption}")
            
            response = {
                "status": "success",
                "message": "Image processed successfully",
                "is_duplicate": is_duplicate,
                "caption": caption
            }
            
            if duplicate_type:
                response["duplicate_type"] = duplicate_type
                
                if duplicate_type == "image":
                    response["message"] = "Image already exists in the database"
                    response["image_key"] = image_key
                elif duplicate_type == "caption":
                    response["message"] = "Caption already exists in the database"
            else:
                response["image_key"] = image_key
                response["message"] = "Image uploaded successfully"
            
            return JSONResponse(content=response)
            
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
