"""
video_engine.py — Sora 2 video generation via Microsoft Foundry.
Uses the official OpenAI Python SDK (client.videos.create/retrieve/download_content).
Generates video clips from text prompts, polls for completion, and saves to local files.
"""

import os
import time
import tempfile
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# --- Configuration ---
AZURE_VIDEO_ENDPOINT = os.environ.get("AZURE_VIDEO_ENDPOINT", "")
AZURE_API_KEY = os.environ.get("AZURE_AI_API_KEY", "")
SORA_MODEL = os.environ.get("SORA_MODEL", "sora-2")

# Video generation settings
DEFAULT_SIZE = "1280x720"  # 720p landscape
MAX_CLIP_SECONDS = 12  # Sora 2 supports 4/8/12/16/20 (16/20 are pro-only)
POLL_INTERVAL = 20  # Seconds between status polls
MAX_POLL_ATTEMPTS = 30  # Max polls (~10 minutes)

# Supported Sora resolutions per model.
# Per OpenAI Sora 2 Prompting Guide (March 2026):
#   sora-2: 720x1280, 1280x720
#   sora-2-pro: 720x1280, 1280x720, 1024x1792, 1792x1024, 1080x1920, 1920x1080
_SORA2_RESOLUTIONS = {
    "1280x720 (720p Landscape)": "1280x720",
    "720x1280 (720p Portrait)": "720x1280",
}
_SORA2_PRO_RESOLUTIONS = {
    "1920x1080 (1080p Landscape)": "1920x1080",
    "1080x1920 (1080p Portrait)": "1080x1920",
    "1792x1024 (HD+ Landscape)": "1792x1024",
    "1024x1792 (HD+ Portrait)": "1024x1792",
    "1280x720 (720p Landscape)": "1280x720",
    "720x1280 (720p Portrait)": "720x1280",
}

def get_available_resolutions(model: str = None) -> dict:
    """Return resolution dict for the configured Sora model."""
    model = (model or SORA_MODEL).lower()
    if "pro" in model:
        return _SORA2_PRO_RESOLUTIONS
    return _SORA2_RESOLUTIONS

def get_resolution_choices(model: str = None) -> list:
    """Return list of resolution display names for GUI dropdown."""
    return list(get_available_resolutions(model).keys())

def get_resolution_value(display_name: str, model: str = None) -> str:
    """Convert display name to actual resolution string."""
    return get_available_resolutions(model).get(display_name, DEFAULT_SIZE)

# Output directory
OUTPUT_DIR = tempfile.mkdtemp(prefix="sora_videos_")

# Initialize OpenAI client pointing to Azure OpenAI Sora 2 endpoint
client = OpenAI(
    base_url=AZURE_VIDEO_ENDPOINT,
    api_key=AZURE_API_KEY,
)


def generate_video_clip(
    prompt: str,
    duration_seconds: int = 8,
    size: str = DEFAULT_SIZE,
    scene_number: int = 0,
) -> dict:
    """
    Submit a video generation request to Sora 2 via Microsoft Foundry.

    Args:
        prompt: Visual description for video generation
        duration_seconds: Clip duration (4, 8, or 12 seconds)
        size: Video resolution (e.g., "1280x720")
        scene_number: Scene identifier for tracking

    Returns:
        {
            "status": "submitted" | "completed" | "failed",
            "job_id": str | None,
            "scene_number": int,
            "file_path": str | None,
            "error": str | None,
        }
    """
    # Snap to valid durations: 4, 8, or 12
    if duration_seconds <= 4:
        duration_seconds = 4
    elif duration_seconds <= 8:
        duration_seconds = 8
    else:
        duration_seconds = 12

    if not AZURE_VIDEO_ENDPOINT:
        return {
            "status": "failed",
            "job_id": None,
            "scene_number": scene_number,
            "file_path": None,
            "error": "AZURE_VIDEO_ENDPOINT not configured",
        }

    try:
        video = client.videos.create(
            model=SORA_MODEL,
            prompt=prompt,
            size=size,
            seconds=duration_seconds,
        )

        # If already completed (unlikely but possible)
        if hasattr(video, 'status') and video.status == "completed":
            file_path = _download_video_by_id(video.id, scene_number)
            return {
                "status": "completed",
                "job_id": video.id,
                "scene_number": scene_number,
                "file_path": file_path,
                "error": None,
            }

        return {
            "status": "submitted",
            "job_id": video.id,
            "scene_number": scene_number,
            "file_path": None,
            "error": None,
        }

    except Exception as e:
        return {
            "status": "failed",
            "job_id": None,
            "scene_number": scene_number,
            "file_path": None,
            "error": str(e),
        }


def poll_video_status(job_id: str, scene_number: int = 0) -> dict:
    """
    Poll for video generation completion using client.videos.retrieve().
    """
    try:
        video = client.videos.retrieve(job_id)
        status = video.status.lower() if hasattr(video, 'status') else "unknown"

        if status == "completed":
            file_path = _download_video_by_id(job_id, scene_number)
            return {
                "status": "completed",
                "job_id": job_id,
                "scene_number": scene_number,
                "file_path": file_path,
                "error": None,
            }
        elif status == "failed":
            error_msg = str(video.error) if hasattr(video, 'error') else "Video generation failed"
            return {
                "status": "failed",
                "job_id": job_id,
                "scene_number": scene_number,
                "file_path": None,
                "error": error_msg,
            }
        else:
            # queued, in_progress
            return {
                "status": "processing",
                "job_id": job_id,
                "scene_number": scene_number,
                "file_path": None,
                "error": None,
            }

    except Exception as e:
        return {
            "status": "failed",
            "job_id": job_id,
            "scene_number": scene_number,
            "file_path": None,
            "error": str(e),
        }


def generate_and_wait(
    prompt: str,
    duration_seconds: int = 8,
    size: str = DEFAULT_SIZE,
    scene_number: int = 0,
    progress_callback=None,
) -> dict:
    """
    Generate a video clip and wait for completion (with polling).
    """
    result = generate_video_clip(prompt, duration_seconds, size, scene_number)

    if result["status"] == "completed":
        return result

    if result["status"] == "failed":
        return result

    # Poll for completion
    job_id = result["job_id"]
    for attempt in range(MAX_POLL_ATTEMPTS):
        time.sleep(POLL_INTERVAL)

        if progress_callback:
            progress_callback(
                f"   Scene {scene_number}: Generating video... ({(attempt + 1) * POLL_INTERVAL}s elapsed)"
            )

        poll_result = poll_video_status(job_id, scene_number)

        if poll_result["status"] == "completed":
            return poll_result
        elif poll_result["status"] == "failed":
            return poll_result
        # else: still processing, continue polling

    return {
        "status": "failed",
        "job_id": job_id,
        "scene_number": scene_number,
        "file_path": None,
        "error": "Timeout: Video generation took too long",
    }


def generate_all_scenes(
    script: dict,
    size: str = DEFAULT_SIZE,
    progress_callback=None,
) -> list:
    """
    Generate video clips for all scenes in a script.

    Args:
        script: Parsed video script with 'scenes' list
        size: Video resolution
        progress_callback: Function to call with status updates

    Returns:
        List of result dicts for each scene
    """
    scenes = script.get("scenes", [])
    results = []

    for i, scene in enumerate(scenes):
        scene_num = scene.get("scene_number", i + 1)
        prompt = scene.get("visual_description", "")
        duration = scene.get("duration_seconds", 8)

        if progress_callback:
            progress_callback(
                f"🎬 Generating scene {scene_num}/{len(scenes)}: {prompt[:60]}..."
            )

        result = generate_and_wait(
            prompt=prompt,
            duration_seconds=duration,
            size=size,
            scene_number=scene_num,
            progress_callback=progress_callback,
        )

        results.append(result)

        if progress_callback:
            if result["status"] == "completed":
                progress_callback(f"✅ Scene {scene_num}/{len(scenes)} complete")
            else:
                progress_callback(
                    f"⚠️ Scene {scene_num}/{len(scenes)} failed: {result.get('error', 'unknown')}"
                )

    return results


def _download_video_by_id(video_id: str, scene_number: int) -> str:
    """Download a completed video using the SDK."""
    file_path = os.path.join(OUTPUT_DIR, f"scene_{scene_number:03d}.mp4")
    content = client.videos.download_content(video_id, variant="video")
    content.write_to_file(file_path)
    return file_path
