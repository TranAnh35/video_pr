from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from pathlib import Path
from app.config.logging_setup import setup_logging
from app.web.api.routers import api_router
import logging
import subprocess
import os
import time

setup_logging()
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Video Processing API...")
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except FileNotFoundError:
        logger.error("FFmpeg not found. Please ensure FFmpeg is installed.")
        raise RuntimeError("FFmpeg not found")
    
    for dir_path in [UPLOAD_DIR, OUTPUT_DIR]:
        try:
            dir_path.mkdir(parents=True, exist_ok=True)
            if not os.access(str(dir_path), os.W_OK):
                logger.error(f"No write permission for directory: {dir_path}")
                raise RuntimeError(f"No write permission for {dir_path}")
        except Exception as e:
            logger.error(f"Error creating directory {dir_path}: {str(e)}")
            raise
    
    yield
    logger.info("Shutting down Video Processing API...")

app = FastAPI(
    title="Video Processing API",
    description="API for processing videos, detecting scenes, and extracting frames",
    version="1.0.0",
    lifespan=lifespan
)

UPLOAD_DIR = Path("uploads")
OUTPUT_DIR = Path("output")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response

app.include_router(api_router)

@app.get("/", summary="Root endpoint", tags=["Root"])
async def root():
    """
    Root endpoint for the API.
    Returns a welcome message.
    """
    return {
        "status": "online",
        "message": "Welcome to the Video Processing API",
        "docs_url": "/docs"
    }

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    error_id = str(time.time())
    logger.error(f"Error ID: {error_id} - Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": "An unexpected error occurred",
            "error_id": error_id
        }
    )