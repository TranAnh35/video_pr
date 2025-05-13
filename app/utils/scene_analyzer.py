import logging
import subprocess
import os
import re
from pathlib import Path

logger = logging.getLogger(__name__)

def detect_scenes_in_video(video_path: str, threshold: float = 0.3, threads: int = 0) -> list | None:
    """
    Detects scenes in a video file using FFmpeg with the select and showinfo filters.

    Args:
        video_path (str): The path to the input video file.
        threshold (float): The scene detection threshold (0.0 to 1.0).
                           Lower values detect more scene changes.
        threads (int): The number of threads for FFmpeg to use (0 for auto).

    Returns:
        list | None: A list of (start_timecode, end_timecode) tuples for each detected scene.
                     Returns an empty list if no scenes are detected but the process was successful.
                     Returns None if an error occurs during scene detection.
    """
    if not os.path.exists(video_path):
        logger.error(f"Video file not found: {video_path}")
        return None

    logger.info(f"Starting scene detection for: {video_path}")

    try:
        command = [
            "ffmpeg", "-i", video_path,
            "-vf", f"select='gt(scene,{threshold})',showinfo",
            "-threads", str(threads),
            "-f", "null", "-"
        ]

        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        if result.returncode != 0:
            logger.error("FFmpeg failed.")
            logger.error(result.stderr)
            return None

        timestamps = []
        for line in result.stderr.splitlines():
            if "showinfo" in line:
                match = re.search(r'pts_time:([\d.]+)', line)
                if match:
                    timestamps.append(float(match.group(1)))

        logger.debug(f"Scene change timestamps: {timestamps}")

        if not timestamps:
            logger.warning("No scene change detected.")
            return []

        scene_list = []
        prev_time = 0.0
        for ts in timestamps:
            scene_list.append((format_timecode(prev_time), format_timecode(ts)))
            prev_time = ts

        duration_cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path
        ]
        duration_result = subprocess.run(duration_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        if duration_result.returncode == 0:
            try:
                duration = float(duration_result.stdout.strip())
                if duration > prev_time:
                    scene_list.append((format_timecode(prev_time), format_timecode(duration)))
            except ValueError:
                logger.warning("Could not parse video duration.")

        logger.info(f"Detected {len(scene_list)} scenes.")
        return scene_list

    except Exception as e:
        logger.error(f"Scene detection failed: {e}", exc_info=True)
        return None


def format_timecode(seconds: float) -> str:
    """
    Converts time in seconds to HH:MM:SS.mmm timecode format.

    Args:
        seconds (float): Time in seconds.

    Returns:
        str: Timecode string in HH:MM:SS.mmm format.
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


if __name__ == '__main__':
    from app.config.logging_setup import setup_logging
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Testing scene_analyzer")

    test_relative_path = "resource/Dataset/7Up.mp4"
    script_dir = os.path.dirname(__file__)
    project_root = Path(script_dir).parents[1]
    test_video = project_root / test_relative_path

    logger.info(f"Checking for test video at: {test_video}")

    if test_video.exists():
        logger.info(f"Attempting to detect scenes in {test_video}")
        scenes = detect_scenes_in_video(str(test_video), threshold=0.3, threads=0)
        if scenes is not None:
            if scenes:
                logger.info(f"Detected {len(scenes)} scenes:")
                for i, (start, end) in enumerate(scenes):
                    logger.info(f"  Scene {i+1}: {start} --> {end}")
            else:
                logger.warning("Scene detection completed but no scenes were detected.")
        else:
            logger.error("Scene detection failed due to an error.")
    else:
        logger.error(f"Test video not found at {test_video}. Please ensure the path and file exist.")