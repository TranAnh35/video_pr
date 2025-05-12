# app/video_processor.py
import os
import shutil
import logging
from multiprocessing import Pool, cpu_count
from pathlib import Path
import traceback

from app.utils.scene_analyzer import detect_scenes_in_video
from app.utils.video_cli import extract_frame_at_timestamp, cut_scene

logger = logging.getLogger(__name__)

def _process_scene_segment(args_tuple):
    """
    Worker function for multiprocessing. Extracts a frame and cuts a scene segment.

    Args:
        args_tuple (tuple): A tuple containing:
            - video_path (str): Path to the source video.
            - start_time (str): Start timecode of the scene.
            - end_time (str): End timecode of the scene.
            - frame_output_path (str): Path to save the extracted frame.
            - scene_clip_output_path (str): Path to save the cut scene clip.
            - threads (int): Number of threads for FFmpeg.

    Returns:
        tuple[bool, bool]: A tuple (frame_success, scene_cut_success).
    """
    video_path, start_time, end_time, frame_output_path, scene_clip_output_path, threads = args_tuple
    try:
        Path(frame_output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(scene_clip_output_path).parent.mkdir(parents=True, exist_ok=True)

        frame_success = extract_frame_at_timestamp(video_path, start_time, frame_output_path, threads)
        scene_cut_success = cut_scene(video_path, start_time, end_time, scene_clip_output_path, threads)
        return frame_success, scene_cut_success
    except Exception as e:
        logger.error(f"Error in worker process for scene {start_time}-{end_time} of {video_path}: {e}\n{traceback.format_exc()}")
        return False, False


def process_video(video_path: str, base_output_dir: str, threshold: float = 0.3, threads_per_ffmpeg: int = 0, num_workers: int = 0) -> bool:
    """
    Processes a video file: detects scenes, extracts a representative frame for each scene,
    and cuts each scene into a separate video clip.

    The cut scenes are re-encoded using libx264 for video and audio is copied.

    Args:
        video_path (str): Path to the input video file.
        base_output_dir (str): Base directory to save the processing results.
                               A subdirectory named after the video will be created here.
        threshold (float): Scene detection threshold (0.0 to 1.0).
        threads_per_ffmpeg (int): Number of threads for each FFmpeg process (0 for auto).
        num_workers (int): Number of parallel worker processes for scene processing
                           (0 to use cpu_count).

    Returns:
        bool: True if processing completed (potentially with minor errors for some scenes),
              False if a critical error occurred or no output was produced from detected scenes.
    """
    if not os.path.exists(video_path):
        logger.error(f"Video file not found: {video_path}. Skipping.")
        return False

    logger.info(f"Starting processing for video: {video_path}")

    video_name_stem = Path(video_path).stem
    video_output_base = Path(base_output_dir) / video_name_stem

    if video_output_base.exists():
        logger.warning(f"Removing existing output directory for {video_name_stem}: {video_output_base}")
        try:
            shutil.rmtree(video_output_base)
        except OSError as e:
            logger.error(f"Error removing directory {video_output_base}: {e}. Skipping video.")
            return False

    try:
        video_output_base.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        logger.warning(f"Directory {video_output_base} already existed unexpectedly. Trying to continue.")
    except Exception as e:
        logger.error(f"Could not create base output directory {video_output_base}: {e}")
        return False

    frame_output_dir = video_output_base / "scene_frames"
    cut_scenes_dir = video_output_base / "cut_scenes"

    try:
        frame_output_dir.mkdir(parents=True, exist_ok=True)
        cut_scenes_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.error(f"Could not create subdirectories under {video_output_base}: {e}")
        if video_output_base.exists() and not any(video_output_base.iterdir()):
            shutil.rmtree(video_output_base, ignore_errors=True)
        return False

    scene_list = detect_scenes_in_video(video_path, threshold=threshold, threads=threads_per_ffmpeg)

    if scene_list is None:
        logger.error(f"Failed to detect scenes for {video_name_stem} due to an error. Skipping.")
        if video_output_base.exists() and not any(video_output_base.iterdir()):
            shutil.rmtree(video_output_base, ignore_errors=True)
        return False
    
    if not scene_list:
        logger.warning(f"No scenes detected in {video_name_stem} with threshold={threshold}.")
        if video_output_base.exists() and not any(video_output_base.iterdir()):
            shutil.rmtree(video_output_base, ignore_errors=True)
        return True

    logger.info(f"Detected {len(scene_list)} scenes. Extracting frames and cutting scenes...")

    args_list = []
    video_extension = Path(video_path).suffix
    for i, (start_time, end_time) in enumerate(scene_list):
        scene_index = i + 1

        frame_filename = f"frame_{scene_index:02d}.jpg"
        scene_clip_filename = f"scene_{scene_index:02d}{video_extension}"

        frame_path = frame_output_dir / frame_filename
        scene_clip_path = cut_scenes_dir / scene_clip_filename
        
        args_list.append((str(video_path), start_time, end_time, str(frame_path), str(scene_clip_path), threads_per_ffmpeg))

    pool_workers = num_workers if num_workers > 0 else cpu_count()
    if threads_per_ffmpeg > 1:
        max_workers_by_threads = max(1, cpu_count() // threads_per_ffmpeg)
        pool_workers = min(pool_workers, max_workers_by_threads)
    if args_list:
        pool_workers = min(pool_workers, len(args_list))
    else:
        pool_workers = 0

    results = []
    if args_list:
        logger.info(f"Processing {len(args_list)} scenes using {pool_workers} worker(s).")
        actual_pool_workers = max(1, pool_workers) if args_list else 0
        if actual_pool_workers > 0:
            with Pool(processes=actual_pool_workers) as pool:
                results = pool.map(_process_scene_segment, args_list)
        else:
            logger.info("Processing scenes sequentially as pool_workers is 0 or 1.")
            for arg_set in args_list:
                results.append(_process_scene_segment(arg_set))
    else:
        logger.info("No valid scenes to process after filtering.")

    successful_frames = sum(1 for r in results if r[0])
    successful_cuts = sum(1 for r in results if r[1])

    logger.info(f"Extracted {successful_frames}/{len(scene_list)} frames successfully.")
    logger.info(f"Cut {successful_cuts}/{len(scene_list)} scenes successfully.")

    if successful_frames == 0 and frame_output_dir.exists() and not any(frame_output_dir.iterdir()):
        logger.warning(f"No frames extracted. Deleting empty frame output directory: {frame_output_dir}")
        shutil.rmtree(frame_output_dir, ignore_errors=True)
    
    if successful_cuts == 0 and cut_scenes_dir.exists() and not any(cut_scenes_dir.iterdir()):
        logger.warning(f"No scenes cut. Deleting empty cut scenes directory: {cut_scenes_dir}")
        shutil.rmtree(cut_scenes_dir, ignore_errors=True)

    if video_output_base.exists() and not any(video_output_base.iterdir()):
        logger.warning(f"Video output base directory {video_output_base} is empty. Deleting.")
        shutil.rmtree(video_output_base, ignore_errors=True)

    if successful_frames == 0 and successful_cuts == 0 and len(scene_list) > 0:
        logger.warning(f"No frames extracted AND no scenes cut for {video_name_stem}, although scenes were detected.")
        return False

    logger.info(f"Finished processing video: {video_path}")
    return True