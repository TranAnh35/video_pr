from fastapi import APIRouter
from . import video, image_upload, search, docs, image_management

api_router = APIRouter()

api_router.include_router(video.router, prefix="/api/detect", tags=["VIDEO"])
api_router.include_router(image_upload.router, prefix="/api/images", tags=["IMAGE"])
api_router.include_router(image_management.router, prefix="/api/images", tags=["IMAGE MANAGEMENT"])
api_router.include_router(search.router, prefix="/api/search", tags=["SEARCH"])
api_router.include_router(docs.router, prefix="/api", tags=["DOCS"])
