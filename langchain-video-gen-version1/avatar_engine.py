"""
avatar_engine.py — Azure AI Speech Avatar for generating talking avatar video segments.
Uses Microsoft's Text-to-Speech Avatar API to create a female AI presenter
who introduces the video and provides transitions.
Supports multiple languages: English, Hindi, Telugu, Kannada, Tamil.
"""

import os
import time
import uuid
import logging
import requests
import tempfile
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# --- Configuration ---
AZURE_SPEECH_KEY = os.environ.get("AZURE_SPEECH_KEY", os.environ.get("AZURE_AI_API_KEY", ""))
AZURE_SPEECH_REGION = os.environ.get("AZURE_SPEECH_REGION", "eastus")

# Avatar API endpoint
AVATAR_API_BASE = f"https://{AZURE_SPEECH_REGION}.api.cognitive.microsoft.com"
AVATAR_API_VERSION = "2024-08-01"

# Avatar characters — verified Azure Speech Avatar characters
AVATAR_CATALOG = {
    # Female avatars
    "Lisa - Casual Sitting": {"character": "lisa", "style": "casual-sitting", "type": "full_body", "gender": "female"},
    "Lisa - Graceful Standing": {"character": "lisa", "style": "graceful-standing", "type": "full_body", "gender": "female"},
    "Lisa - Technical Standing": {"character": "lisa", "style": "technical-standing", "type": "full_body", "gender": "female"},
    "Meg - Business": {"character": "meg", "style": "business", "type": "full_body", "gender": "female"},
    "Meg - Casual": {"character": "meg", "style": "casual", "type": "full_body", "gender": "female"},
    "Lori - Graceful": {"character": "lori", "style": "graceful", "type": "full_body", "gender": "female"},
    "Lori - Casual": {"character": "lori", "style": "casual", "type": "full_body", "gender": "female"},
    "Jenny": {"character": "jenny", "style": None, "type": "talking_head", "gender": "female"},
    "Aria": {"character": "aria", "style": None, "type": "talking_head", "gender": "female"},
    "Nancy": {"character": "nancy", "style": None, "type": "talking_head", "gender": "female"},
    "Yuna": {"character": "yuna", "style": None, "type": "talking_head", "gender": "female"},
    # Male avatars
    "Harry - Business": {"character": "harry", "style": "business", "type": "full_body", "gender": "male"},
    "Harry - Casual": {"character": "harry", "style": "casual", "type": "full_body", "gender": "male"},
    "Harry - Technical": {"character": "harry", "style": "technical", "type": "full_body", "gender": "male"},
    "Max - Business": {"character": "max", "style": "business", "type": "full_body", "gender": "male"},
    "Max - Casual": {"character": "max", "style": "casual", "type": "full_body", "gender": "male"},
    "Jeff": {"character": "jeff", "style": None, "type": "talking_head", "gender": "male"},
    "Guy": {"character": "guy", "style": None, "type": "talking_head", "gender": "male"},
    "Davis": {"character": "davis", "style": None, "type": "talking_head", "gender": "male"},
    "Jason": {"character": "jason", "style": None, "type": "talking_head", "gender": "male"},
    "Tony": {"character": "tony", "style": None, "type": "talking_head", "gender": "male"},
    "Brandon": {"character": "brandon", "style": None, "type": "talking_head", "gender": "male"},
}

# Default avatar per gender (backward compat)
AVATAR_CONFIG = {
    "female": {"character": "lisa", "style": "graceful-standing"},
    "male": {"character": "harry", "style": "business"},
}

def get_avatar_choices() -> list:
    """Return list of avatar names for GUI dropdown."""
    return list(AVATAR_CATALOG.keys())

def get_avatar_config(avatar_name: str, voice_gender: str = "female") -> dict:
    """Get avatar character/style config from the catalog name."""
    if avatar_name and avatar_name in AVATAR_CATALOG:
        entry = AVATAR_CATALOG[avatar_name]
        return {"character": entry["character"], "style": entry["style"]}
    # Fallback to default based on gender
    return AVATAR_CONFIG.get(voice_gender, AVATAR_CONFIG["female"])

# Output directory
OUTPUT_DIR = tempfile.mkdtemp(prefix="avatar_videos_")

# Language → Azure Neural Voice mapping per gender
AVATAR_VOICE_MAP = {
    "english": {
        "female": "en-IN-NeerjaNeural",
        "male": "en-IN-PrabhatNeural",
        "locale": "en-IN",
        "label": "English (Indian)",
    },
    "hindi": {
        "female": "hi-IN-SwaraNeural",
        "male": "hi-IN-MadhurNeural",
        "locale": "hi-IN",
        "label": "Hindi (हिन्दी)",
    },
    "telugu": {
        "female": "te-IN-ShrutiNeural",
        "male": "te-IN-MohanNeural",
        "locale": "te-IN",
        "label": "Telugu (తెలుగు)",
    },
    "kannada": {
        "female": "kn-IN-SapnaNeural",
        "male": "kn-IN-GaganNeural",
        "locale": "kn-IN",
        "label": "Kannada (ಕನ್ನಡ)",
    },
    "tamil": {
        "female": "ta-IN-PallaviNeural",
        "male": "ta-IN-ValluvarNeural",
        "locale": "ta-IN",
        "label": "Tamil (தமிழ்)",
    },
}

# Polling settings
POLL_INTERVAL = 5
MAX_POLL_ATTEMPTS = 120  # 10 minutes
MAX_SUBMIT_RETRIES = 3   # Retry transient HTTP errors on submit


def _submit_with_retry(url, payload, headers, max_retries=MAX_SUBMIT_RETRIES):
    """Submit avatar synthesis request with retry for transient errors (429, 5xx)."""
    for attempt in range(max_retries):
        try:
            response = requests.put(url, json=payload, headers=headers, timeout=30)
            if response.status_code in (429, 500, 502, 503, 504) and attempt < max_retries - 1:
                wait = 10 * (attempt + 1)
                logger.warning(
                    "Avatar submit got HTTP %s, retrying in %ss (attempt %s/%s)...",
                    response.status_code, wait, attempt + 1, max_retries,
                )
                time.sleep(wait)
                continue
            response.raise_for_status()
            return response
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                time.sleep(10)
                continue
            raise
    raise RuntimeError("Avatar submit failed after all retries")


def generate_avatar_video(
    text: str,
    language: str = "english",
    voice_gender: str = "female",
    segment_type: str = "intro",
    avatar_name: str = None,
    progress_callback=None,
) -> dict:
    """
    Generate a talking avatar video segment using Azure AI Speech Avatar API.

    Args:
        text: The text for the avatar to speak
        language: Language key (english, hindi, telugu, kannada, tamil)
        voice_gender: "male" or "female"
        segment_type: "intro", "transition", or "outro" — for file naming
        avatar_name: Selected avatar from AVATAR_CATALOG (optional, falls back to gender default)
        progress_callback: Status callback function

    Returns:
        {
            "status": "completed" | "failed",
            "file_path": str | None,
            "duration_estimate": float,
            "error": str | None,
        }
    """
    if not text or not text.strip():
        return {
            "status": "failed",
            "file_path": None,
            "duration_estimate": 0,
            "error": "Empty text for avatar",
        }

    voice_config = AVATAR_VOICE_MAP.get(language, AVATAR_VOICE_MAP["english"])
    voice_name = voice_config.get(voice_gender, voice_config["female"])
    avatar_cfg = get_avatar_config(avatar_name, voice_gender)
    synthesis_id = str(uuid.uuid4())

    url = f"{AVATAR_API_BASE}/avatar/batchsyntheses/{synthesis_id}?api-version={AVATAR_API_VERSION}"

    headers = {
        "Ocp-Apim-Subscription-Key": AZURE_SPEECH_KEY,
        "Content-Type": "application/json",
    }

    avatar_config = {
        "talkingAvatarCharacter": avatar_cfg["character"],
        "videoFormat": "mp4",
        "videoCodec": "h264",
        # Higher bitrate preserves fine mouth-edge detail for lip sync.
        "bitrateKbps": 2000,
        # Dark neutral background blends into any video style.
        "backgroundColor": "#1A1A1AFF",
    }
    if avatar_cfg.get("style"):
        avatar_config["talkingAvatarStyle"] = avatar_cfg["style"]

    # Use PlainText input — Azure Avatar's internal pipeline generates perfectly
    # aligned visemes (mouth shapes) when it controls both TTS and animation.
    # SSML interferes because prosody/break modifications shift audio timing
    # without proportionally adjusting the viseme schedule.
    payload = {
        "inputKind": "PlainText",
        "synthesisConfig": {
            "voice": voice_name,
        },
        "avatarConfig": avatar_config,
        "inputs": [
            {
                "content": text,
            }
        ],
    }

    try:
        if progress_callback:
            progress_callback(f"🧑‍💼 Submitting avatar {segment_type} generation ({voice_config['label']})...")

        _submit_with_retry(url, payload, headers)

        # Poll for completion
        return _poll_avatar_status(
            synthesis_id=synthesis_id,
            segment_type=segment_type,
            text=text,
            progress_callback=progress_callback,
        )

    except requests.exceptions.HTTPError as e:
        return {
            "status": "failed",
            "file_path": None,
            "duration_estimate": 0,
            "error": f"Avatar HTTP {e.response.status_code}: {e.response.text[:300]}",
        }
    except Exception as e:
        return {
            "status": "failed",
            "file_path": None,
            "duration_estimate": 0,
            "error": str(e),
        }


def _poll_avatar_status(
    synthesis_id: str,
    segment_type: str,
    text: str,
    progress_callback=None,
) -> dict:
    """Poll for avatar batch synthesis completion."""
    url = f"{AVATAR_API_BASE}/avatar/batchsyntheses/{synthesis_id}?api-version={AVATAR_API_VERSION}"
    headers = {
        "Ocp-Apim-Subscription-Key": AZURE_SPEECH_KEY,
    }

    for attempt in range(MAX_POLL_ATTEMPTS):
        time.sleep(POLL_INTERVAL)

        if progress_callback and attempt % 3 == 0:
            progress_callback(
                f"🧑‍💼 Avatar {segment_type}: generating... ({attempt * POLL_INTERVAL}s elapsed)"
            )

        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            result = response.json()

            status = result.get("status", "").lower()

            if status == "succeeded":
                # Download the avatar video
                outputs = result.get("outputs", {})
                video_url = outputs.get("result")

                if video_url:
                    file_path = _download_avatar_video(video_url, segment_type)
                    word_count = len(text.split())
                    duration_estimate = word_count / 2.5

                    return {
                        "status": "completed",
                        "file_path": file_path,
                        "duration_estimate": duration_estimate,
                        "error": None,
                    }
                else:
                    return {
                        "status": "failed",
                        "file_path": None,
                        "duration_estimate": 0,
                        "error": "Avatar succeeded but no video URL in response",
                    }

            elif status == "failed":
                error_msg = result.get("properties", {}).get("error", {}).get("message", "Unknown error")
                return {
                    "status": "failed",
                    "file_path": None,
                    "duration_estimate": 0,
                    "error": f"Avatar generation failed: {error_msg}",
                }

            # Still running — continue polling

        except Exception as e:
            if attempt == MAX_POLL_ATTEMPTS - 1:
                return {
                    "status": "failed",
                    "file_path": None,
                    "duration_estimate": 0,
                    "error": f"Polling error: {str(e)}",
                }

    return {
        "status": "failed",
        "file_path": None,
        "duration_estimate": 0,
        "error": "Timeout: Avatar generation took too long",
    }


def _download_avatar_video(url: str, segment_type: str) -> str:
    """Download generated avatar video using streaming to handle large files."""
    file_path = os.path.join(OUTPUT_DIR, f"avatar_{segment_type}.mp4")
    with requests.get(url, timeout=180, stream=True) as response:
        response.raise_for_status()
        with open(file_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
    return file_path


def generate_intro_and_outro(
    script: dict,
    language: str = "english",
    voice_gender: str = "female",
    avatar_name: str = None,
    progress_callback=None,
) -> dict:
    """
    Generate avatar intro and outro segments for the video.

    The avatar (selected by user or default based on voice_gender) introduces the topic and closes the video.

    Args:
        script: Video script dict with 'title' and 'scenes'
        language: Language key
        voice_gender: "male" or "female"
        avatar_name: Selected avatar from AVATAR_CATALOG
        progress_callback: Status callback

    Returns:
        {
            "intro": result_dict,
            "outro": result_dict,
        }
    """
    title = script.get("title", "this video")

    # Use script-provided intro/outro narration (from GPT) if available,
    # otherwise fall back to generic text
    intro_text = script.get("intro_narration", "")
    outro_text = script.get("outro_narration", "")

    # Fallback generic texts if GPT didn't provide them
    if not intro_text:
        intro_texts = {
            "english": (
                f"Hello and welcome! In this video, we'll be exploring: {title}. "
                f"Let's dive right in."
            ),
            "hindi": (
                f"नमस्ते और स्वागत है! इस वीडियो में हम जानेंगे: {title}। "
                f"आइए शुरू करते हैं।"
            ),
            "telugu": (
                f"నమస్కారం మరియు స్వాగతం! ఈ వీడియోలో మనం తెలుసుకుందాం: {title}. "
                f"మొదలు పెడదాం."
            ),
            "kannada": (
                f"ನಮಸ್ಕಾರ ಮತ್ತು ಸ್ವಾಗತ! ಈ ವೀಡಿಯೊದಲ್ಲಿ ನಾವು ತಿಳಿಯೋಣ: {title}. "
                f"ಪ್ರಾರಂಭಿಸೋಣ."
            ),
            "tamil": (
                f"வணக்கம் மற்றும் வரவேற்பு! இந்த வீடியோவில் நாம் அறிவோம்: {title}. "
                f"தொடங்குவோம்."
            ),
        }
        intro_text = intro_texts.get(language, intro_texts["english"])

    if not outro_text:
        outro_texts = {
            "english": (
                "Thank you for watching! I hope you found this video informative and useful. "
                "See you next time!"
            ),
            "hindi": "देखने के लिए धन्यवाद! अगला वीडियो में मिलते हैं!",
            "telugu": "చూసినందుకు ధన్యవాదాలు! తదుపరి వీడియోలో కలుద్దాం!",
            "kannada": "ನೋಡಿದ್ದಕ್ಕೆ ಧನ್ಯವಾದಗಳು! ಮುಂದಿನ ವೀಡಿಯೊದಲ್ಲಿ ಭೇಟಿಯಾಗೋಣ!",
            "tamil": "பார்த்ததற்கு நன்றி! அடுத்த வீடியோவில் சந்திப்போம்!",
        }
        outro_text = outro_texts.get(language, outro_texts["english"])

    if progress_callback:
        progress_callback("🧑‍💼 Generating avatar intro segment...")

    intro_result = generate_avatar_video(
        text=intro_text,
        language=language,
        voice_gender=voice_gender,
        segment_type="intro",
        avatar_name=avatar_name,
        progress_callback=progress_callback,
    )

    # Generate mid-video avatar segment if script provides it
    mid_result = {"status": "skipped", "file_path": None, "duration_estimate": 0, "error": None}
    mid_text = script.get("mid_narration", "")
    if mid_text:
        if progress_callback:
            progress_callback("🧑‍💼 Generating avatar mid-video segment...")
        mid_result = generate_avatar_video(
            text=mid_text,
            language=language,
            voice_gender=voice_gender,
            segment_type="mid",
            avatar_name=avatar_name,
            progress_callback=progress_callback,
        )

    if progress_callback:
        progress_callback("🧑‍💼 Generating avatar outro segment...")

    outro_result = generate_avatar_video(
        text=outro_text,
        language=language,
        voice_gender=voice_gender,
        segment_type="outro",
        avatar_name=avatar_name,
        progress_callback=progress_callback,
    )

    return {
        "intro": intro_result,
        "mid": mid_result,
        "outro": outro_result,
    }


def get_supported_languages() -> dict:
    """Return the supported languages with labels."""
    return {key: val["label"] for key, val in AVATAR_VOICE_MAP.items()}
