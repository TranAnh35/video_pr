"""
API documentation related endpoints.
"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()

@router.get("/endpoints/", summary="List all available API endpoints")
async def list_endpoints():
    """
    List all available API endpoints with descriptions
    
    Returns:
        JSON response with endpoint details
    """
    endpoints = [
        {
            "path": "/api/process-video/",
            "method": "POST",
            "description": "Process a video to detect scenes and extract frames"
        },
        {
            "path": "/api/frames/{video_name}/{frame_name}",
            "method": "GET",
            "description": "Get a frame image from processed video"
        },
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
        }
    ]
    
    return JSONResponse(content={
        "status": "success",
        "endpoints": endpoints
    })
