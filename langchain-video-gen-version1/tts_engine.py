"""
tts_engine.py — Text-to-Speech via Azure Cognitive Services Speech SDK.
Generates narration audio for video scenes using Azure Neural Voices.
Supports male/female voice selection and multiple languages
(English, Hindi, Telugu, Kannada, Tamil).
"""

import os
import html
import logging
import tempfile
from dotenv import load_dotenv

import azure.cognitiveservices.speech as speechsdk

load_dotenv()

logger = logging.getLogger(__name__)

# --- Configuration ---
AZURE_SPEECH_ENDPOINT = os.environ.get("AZURE_SPEECH_ENDPOINT", "")
AZURE_SPEECH_KEY = os.environ.get("AZURE_SPEECH_KEY", "")
AZURE_SPEECH_REGION = os.environ.get("AZURE_SPEECH_REGION", "eastus")

# Voice mapping — Azure Neural Voices per language and gender
# locale key is used as xml:lang in SSML for correct pronunciation
VOICE_MAP = {
    "english": {
        "male": "en-IN-PrabhatNeural",
        "female": "en-IN-NeerjaNeural",
        "locale": "en-IN",
    },
    "hindi": {
        "male": "hi-IN-MadhurNeural",
        "female": "hi-IN-SwaraNeural",
        "locale": "hi-IN",
    },
    "telugu": {
        "male": "te-IN-MohanNeural",
        "female": "te-IN-ShrutiNeural",
        "locale": "te-IN",
    },
    "kannada": {
        "male": "kn-IN-GaganNeural",
        "female": "kn-IN-SapnaNeural",
        "locale": "kn-IN",
    },
    "tamil": {
        "male": "ta-IN-ValluvarNeural",
        "female": "ta-IN-PallaviNeural",
        "locale": "ta-IN",
    },
}

# Language configuration
LANGUAGE_CONFIG = {
    "english": {"code": "en", "label": "English"},
    "hindi": {"code": "hi", "label": "Hindi (हिन्दी)"},
    "telugu": {"code": "te", "label": "Telugu (తెలుగు)"},
    "kannada": {"code": "kn", "label": "Kannada (ಕನ್ನಡ)"},
    "tamil": {"code": "ta", "label": "Tamil (தமிழ்)"},
}

# Output directory
OUTPUT_DIR = tempfile.mkdtemp(prefix="tts_audio_")


def _get_speech_config(voice_name: str) -> speechsdk.SpeechConfig:
    """Create a SpeechConfig with the given voice."""
    speech_config = speechsdk.SpeechConfig(
        subscription=AZURE_SPEECH_KEY,
        region=AZURE_SPEECH_REGION,
    )
    speech_config.speech_synthesis_voice_name = voice_name
    return speech_config


def generate_narration(
    text: str,
    voice_gender: str = "female",
    language: str = "english",
    scene_number: int = 0,
    output_format: str = "mp3",
) -> dict:
    """
    Generate TTS audio for a narration text using Azure Speech SDK.

    Args:
        text: The narration text to speak
        voice_gender: "male" or "female"
        language: Language key (english, hindi, telugu, kannada, tamil)
        scene_number: Scene identifier
        output_format: Audio format (mp3 or wav)

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
            "error": "Empty narration text",
        }

    # Get the appropriate voice for language + gender
    lang_voices = VOICE_MAP.get(language, VOICE_MAP["english"])
    voice_name = lang_voices.get(voice_gender, lang_voices["female"])

    # Output file path
    file_path = os.path.join(OUTPUT_DIR, f"narration_{scene_number:03d}.{output_format}")

    try:
        speech_config = _get_speech_config(voice_name)

        # Set output format — 24KHz/96kbps gives clear, broadcast-quality narration
        if output_format == "mp3":
            speech_config.set_speech_synthesis_output_format(
                speechsdk.SpeechSynthesisOutputFormat.Audio24Khz96KBitRateMonoMp3
            )
        else:
            speech_config.set_speech_synthesis_output_format(
                speechsdk.SpeechSynthesisOutputFormat.Riff24Khz16BitMonoPcm
            )

        # Output to file
        audio_config = speechsdk.audio.AudioOutputConfig(filename=file_path)
        synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=speech_config,
            audio_config=audio_config,
        )

        # Use SSML with the correct language locale — critical for non-English voices.
        # xml:lang must match the voice locale to avoid mispronunciation.
        # Text is HTML-escaped to prevent malformed XML on special characters.
        locale = VOICE_MAP.get(language, VOICE_MAP["english"])["locale"]
        safe_text = html.escape(text)
        ssml = (
            f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
            f'xmlns:mstts="http://www.w3.org/2001/mstts" xml:lang="{locale}">'
            f'<voice name="{voice_name}">'
            f'<mstts:express-as style="general">'
            f'<break time="250ms"/>'
            f'{safe_text}'
            f'<break time="150ms"/>'
            f'</mstts:express-as>'
            f'</voice></speak>'
        )
        result = synthesizer.speak_ssml_async(ssml).get()

        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            # Estimate duration (~2.5 words per second)
            word_count = len(text.split())
            duration_estimate = word_count / 2.5

            return {
                "status": "completed",
                "file_path": file_path,
                "duration_estimate": duration_estimate,
                "error": None,
            }
        elif result.reason == speechsdk.ResultReason.Canceled:
            cancellation = result.cancellation_details
            error_msg = f"Speech synthesis canceled: {cancellation.reason}"
            if cancellation.reason == speechsdk.CancellationReason.Error:
                error_msg += f" — {cancellation.error_details}"
            return {
                "status": "failed",
                "file_path": None,
                "duration_estimate": 0,
                "error": error_msg,
            }
        else:
            return {
                "status": "failed",
                "file_path": None,
                "duration_estimate": 0,
                "error": f"Unexpected result reason: {result.reason}",
            }

    except Exception as e:
        return {
            "status": "failed",
            "file_path": None,
            "duration_estimate": 0,
            "error": str(e),
        }


def generate_full_narration(
    script: dict,
    voice_gender: str = "female",
    language: str = "english",
    progress_callback=None,
) -> list:
    """
    Generate narration audio for all scenes in a script.

    Args:
        script: Parsed video script with 'scenes' list
        voice_gender: "male" or "female"
        language: Language key (english, hindi, telugu, kannada, tamil)
        progress_callback: Status update callback

    Returns:
        List of result dicts for each scene's narration
    """
    scenes = script.get("scenes", [])
    results = []

    lang_label = LANGUAGE_CONFIG.get(language, LANGUAGE_CONFIG["english"])["label"]

    for i, scene in enumerate(scenes):
        scene_num = scene.get("scene_number", i + 1)
        narration = scene.get("narration_text", "")

        if progress_callback:
            progress_callback(f"🎙️ Generating narration {scene_num}/{len(scenes)} ({lang_label})...")

        result = generate_narration(
            text=narration,
            voice_gender=voice_gender,
            language=language,
            scene_number=scene_num,
        )
        results.append(result)

        if progress_callback:
            if result["status"] == "completed":
                progress_callback(f"✅ Narration {scene_num}/{len(scenes)} complete")
            else:
                progress_callback(
                    f"⚠️ Narration {scene_num}/{len(scenes)} failed: {result.get('error', 'unknown')}"
                )

    return results


def generate_per_scene_narration(
    script: dict,
    voice_gender: str = "female",
    language: str = "english",
    progress_callback=None,
) -> dict:
    """
    Generate individual TTS audio files for every content scene.

    Returns:
        Dict keyed by scene_number: {scene_number: {status, file_path, duration_estimate, error}}

    This replaces the combined-narration approach and eliminates audio overlap with avatar
    segments. Each scene's audio is later positioned at the exact timeline offset of that
    scene's video clip inside the assembler.
    """
    scenes = script.get("scenes", [])
    lang_label = LANGUAGE_CONFIG.get(language, LANGUAGE_CONFIG["english"])["label"]
    results = {}

    for i, scene in enumerate(scenes):
        scene_num = scene.get("scene_number", i + 1)
        narration = scene.get("narration_text", "")

        if progress_callback:
            progress_callback(
                f"🎙️ Scene narration {i + 1}/{len(scenes)} ({lang_label})..."
            )

        result = generate_narration(
            text=narration,
            voice_gender=voice_gender,
            language=language,
            scene_number=scene_num,
        )
        results[scene_num] = result

        if progress_callback:
            if result["status"] == "completed":
                progress_callback(f"   ✅ Scene {scene_num} narration done")
            else:
                progress_callback(
                    f"   ⚠️ Scene {scene_num} narration failed: {result.get('error', 'unknown')}"
                )

    return results


def generate_combined_narration(
    script: dict,
    voice_gender: str = "female",
    language: str = "english",
    include_intro_outro: bool = False,
    progress_callback=None,
) -> dict:
    """
    (Legacy) Generate narration audio for the CONTENT section only.
    Kept for backward compatibility. Prefer generate_per_scene_narration for production use.

    Returns:
        Single result dict with combined narration file
    """
    scenes = script.get("scenes", [])
    title = script.get("title", "this video")
    lang_label = LANGUAGE_CONFIG.get(language, LANGUAGE_CONFIG["english"])["label"]

    parts = []

    # Only include intro/outro in narration if avatar generation failed (fallback)
    if include_intro_outro:
        intro_text = script.get("intro_narration", "")
        if not intro_text:
            intro_text = f"Hello and welcome! In this video, we'll be exploring: {title}. Let's dive right in."
        parts.append(intro_text)

    # Add scene narrations (this is the content that plays over B-roll)
    for scene in scenes:
        narration = scene.get("narration_text", "")
        if narration:
            parts.append(narration)

    if include_intro_outro:
        outro_text = script.get("outro_narration", "")
        if not outro_text:
            outro_text = "Thank you for watching! See you next time!"
        parts.append(outro_text)

    # Join with pauses
    full_narration = " ... ".join(parts)

    if progress_callback:
        progress_callback(f"🎙️ Generating content narration audio ({lang_label})...")

    result = generate_narration(
        text=full_narration,
        voice_gender=voice_gender,
        language=language,
        scene_number=0,  # Combined file
    )

    if progress_callback:
        if result["status"] == "completed":
            progress_callback("✅ Content narration audio generated")
        else:
            progress_callback(f"⚠️ Narration failed: {result.get('error', 'unknown')}")

    return result
