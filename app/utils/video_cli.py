import os
import subprocess
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def extract_frame_at_timestamp(video_path: str, timestamp: str, output_image_path: str, threads: int = 0) -> bool:
    """
    Extracts a single frame from a video at a specific timestamp.

    Args:
        video_path (str): Path to the source video file.
        timestamp (str): The timestamp to extract the frame from (e.g., '00:00:10.000').
        output_image_path (str): Path to save the extracted image frame.
        threads (int): Number of threads for FFmpeg to use (0 for auto).

    Returns:
        bool: True if frame extraction was successful, False otherwise.
    """
    try:
        Path(output_image_path).parent.mkdir(parents=True, exist_ok=True)

        command = [
            "ffmpeg", "-y",
            "-ss", timestamp,
            "-i", video_path,
            "-frames:v", "1",
            "-q:v", "2",
            "-threads", str(threads),
            "-loglevel", "warning",
            output_image_path
        ]
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        if result.returncode != 0:
            logger.error(f"FFmpeg failed to extract frame at {timestamp}. Error: {result.stderr}")
            return False

        return os.path.exists(output_image_path) and os.path.getsize(output_image_path) > 0

    except Exception as e:
        logger.error(f"Error extracting frame at {timestamp}: {e}")
        return False
    
    
def cut_scene(video_path: str, start_timecode: str, end_timecode: str, output_scene_path: str, threads: int = 0) -> bool:
    """
    Cuts a scene from the source video and saves it as a new file.
    The video is re-encoded using libx264. Audio is copied if present.

    Args:
        video_path (str): Path to the source video file.
        start_timecode (str): The start timecode of the scene (HH:MM:SS.mmm).
        end_timecode (str): The end timecode of the scene (HH:MM:SS.mmm).
        output_scene_path (str): Path to save the cut video scene.
        threads (int): Number of threads for FFmpeg to use (0 for auto).

    Returns:
        bool: True if the scene was cut successfully, False otherwise.
    """
    try:
        Path(output_scene_path).parent.mkdir(parents=True, exist_ok=True)

        command = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-ss", start_timecode,
            "-to", end_timecode,
            "-c:v", "libx264",
            "-threads", str(threads),
            "-loglevel", "warning",
            output_scene_path
        ]

        logger.debug(f"Executing FFmpeg command for cutting scene: {' '.join(command)}")
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)

        if result.returncode != 0:
            logger.error(f"FFmpeg failed to cut scene from {start_timecode} to {end_timecode} for {video_path}. Error: {result.stderr}")
            if os.path.exists(output_scene_path):
                os.remove(output_scene_path)
            return False

        return os.path.exists(output_scene_path) and os.path.getsize(output_scene_path) > 0

    except Exception as e:
        logger.error(f"Error cutting scene from {start_timecode} to {end_timecode} for {video_path}: {e}", exc_info=True)
        return False