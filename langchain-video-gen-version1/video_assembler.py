"""
video_assembler.py — Assembles generated video clips and narration audio
into a final video file using moviepy.
Handles: clip concatenation, audio overlay, duration matching, final export.
Supports: multi-point avatar insertion, logo watermark, text overlays, title card.
"""

import os
import logging
import tempfile
from pathlib import Path
from moviepy import (
    VideoFileClip,
    AudioFileClip,
    concatenate_videoclips,
    ColorClip,
    vfx,
)
from overlay_engine import apply_logo_watermark, apply_text_overlay, generate_title_card

logger = logging.getLogger(__name__)

# Output directory
OUTPUT_DIR = tempfile.mkdtemp(prefix="final_video_")


def assemble_video(
    video_clips: list,
    per_scene_narration: dict,
    script: dict,
    target_duration_seconds: int = 60,
    avatar_segments: dict = None,
    outro_narration_result: dict = None,
    logo_path: str = None,
    logo_position: str = "top-right",
    logo_opacity: float = 0.7,
    enable_text_overlays: bool = True,
    enable_title_card: bool = True,
    title_card_title: str = "",
    title_card_subtitle: str = "",
    progress_callback=None,
) -> dict:
    """
    Assemble video clips, avatar segments, and per-scene narration into a final video.

    Architecture (multi-point avatar):
        [Avatar Intro] → [Content scenes 1st half] → [Avatar Mid] → [Content scenes 2nd half] → [Avatar Outro] → [Title Card]

    Audio architecture (one voice at a time, perfect lip sync):
        - Each clip carries its OWN audio, and clips are simply concatenated.
        - Avatar clips are loaded WITH their original Azure audio attached, so the
          voice stays frame-locked to the mouth movement (accurate lip sync).
        - Content clips are loaded WITHOUT audio, then the matching per-scene TTS
          narration is bound as that clip's own audio (trimmed to clip length).
        - Because audio travels with each clip during concatenation, exactly one
          source is ever audible — the avatar voice during avatar segments and the
          narration during content segments. There is NO global audio composite,
          so the two voices can never overlap.
        - outro_narration_result is bound to the title card's own audio when the
          avatar outro is unavailable.

    Ending guarantee:
        The video ALWAYS ends with a proper conclusion:
          - If avatar outro succeeded → outro clip plays, then title card
          - If avatar outro failed   → outro TTS plays over the title card
        A fade-in (0.5s) opens the video; a fade-to-black (2s) closes it.

    Args:
        video_clips: List of dicts from video_engine (includes scene_number per clip)
        per_scene_narration: Dict {scene_number: narration_result} from tts_engine
        script: The video script
        target_duration_seconds: Target total duration
        avatar_segments: Dict with 'intro', 'mid', and 'outro' avatar result dicts
        outro_narration_result: TTS narration fallback for the ending (used when avatar outro fails)
        logo_path: Path to logo image for watermark
        logo_position: Logo position ('top-right', 'top-left', etc.)
        logo_opacity: Logo opacity (0.0 to 1.0)
        enable_text_overlays: Whether to add text overlays from script
        enable_title_card: Whether to add a final title card
        title_card_title: Title text for the final card
        title_card_subtitle: Subtitle for the final card
        progress_callback: Status update callback

    Returns:
        Result dict with status, file_path, duration, error
    """
    all_opened_clips = []  # track all opened clips for cleanup

    def _safe_close_all():
        for c in all_opened_clips:
            try:
                c.close()
            except Exception:
                pass

    try:
        if progress_callback:
            progress_callback("🎬 Assembling final video...")

        # Collect successfully generated content clips with their scene numbers
        successful_clips = []
        for result in video_clips:
            if result.get("status") == "completed" and result.get("file_path"):
                if os.path.exists(result["file_path"]):
                    successful_clips.append({
                        "path": result["file_path"],
                        "scene_number": result.get("scene_number", 0),
                    })

        if not successful_clips:
            return {
                "status": "failed",
                "file_path": None,
                "duration": 0,
                "error": "No video clips were successfully generated",
            }

        if progress_callback:
            progress_callback(f"📎 Loading {len(successful_clips)} video clips...")

        # --- Determine target resolution from first content clip ---
        target_size = (1280, 720)
        try:
            probe = VideoFileClip(successful_clips[0]["path"])
            all_opened_clips.append(probe)
            target_size = probe.size
        except Exception:
            pass

        # --- Load avatar clips WITH their own audio (frame-locked lip sync) ---
        # CRITICAL: Azure delivers each avatar mp4 perfectly lip-synced. We MUST
        # keep that audio attached to the clip. The previous approach stripped the
        # audio and re-positioned it with a computed float offset inside a global
        # CompositeAudioClip — that float math drifted against the real frame
        # timeline (lip desync) and let the avatar voice bleed past its video into
        # the narrated content (two voices at once). By letting every clip carry
        # its OWN audio, moviepy concatenates audio together with video so the
        # avatar's voice stays frame-aligned to its mouth and only ONE source is
        # ever audible at any instant.
        def _load_avatar_clip(seg_key):
            seg = (avatar_segments or {}).get(seg_key, {}) or {}
            if seg.get("status") != "completed" or not seg.get("file_path"):
                return None
            if not os.path.exists(seg["file_path"]):
                return None
            try:
                clip = VideoFileClip(seg["file_path"])  # WITH audio — do not strip
                all_opened_clips.append(clip)
                if clip.size != target_size:
                    clip = clip.resized(new_size=target_size)
                if progress_callback:
                    progress_callback(
                        f"🧑‍💼 Avatar {seg_key} loaded ({clip.duration:.1f}s, audio attached)"
                    )
                return clip
            except Exception as e:
                if progress_callback:
                    progress_callback(f"⚠️ Could not load avatar {seg_key}: {e}")
                return None

        intro_clip = _load_avatar_clip("intro")
        mid_clip = _load_avatar_clip("mid")
        outro_clip = _load_avatar_clip("outro")

        # --- Load content clips and bind each scene's narration as its OWN audio ---
        # Every content clip carries ONLY its matching narration. There is no
        # global audio composite, so narration can never bleed onto an avatar
        # segment (or vice versa) — exactly one voice plays at any moment, by
        # construction. Narration is trimmed to the clip length so it cannot spill
        # into the next segment; shorter narration simply leaves trailing silence.
        content_clips = []

        for item in successful_clips:
            try:
                clip = VideoFileClip(item["path"]).without_audio()
                all_opened_clips.append(clip)
                if clip.size != target_size:
                    clip = clip.resized(new_size=target_size)

                scene_num = item["scene_number"]
                narr = per_scene_narration.get(scene_num, {})
                if (
                    narr.get("status") == "completed"
                    and narr.get("file_path")
                    and os.path.exists(narr["file_path"])
                ):
                    try:
                        narr_audio = AudioFileClip(narr["file_path"])
                        all_opened_clips.append(narr_audio)
                        if narr_audio.duration > clip.duration:
                            narr_audio = narr_audio.subclipped(0, clip.duration)
                        clip = clip.with_audio(narr_audio)
                    except Exception as e:
                        if progress_callback:
                            progress_callback(
                                f"⚠️ Scene {scene_num} narration audio error: {e}"
                            )
                content_clips.append(clip)
            except Exception as e:
                if progress_callback:
                    progress_callback(f"⚠️ Skipping corrupted clip {item['path']}: {e}")

        if not content_clips:
            _safe_close_all()
            return {
                "status": "failed",
                "file_path": None,
                "duration": 0,
                "error": "All video clips failed to load",
            }

        # --- Build sequence: intro → 1st half → mid → 2nd half → outro ---
        # The avatar always OPENS (intro) and CLOSES (outro) the video; the
        # optional mid segment appears between the two content halves when the
        # script provides mid narration.
        if progress_callback:
            progress_callback("🔗 Building avatar sequence (intro → content → outro)...")

        intro_duration = intro_clip.duration if intro_clip else 0.0
        mid_duration = mid_clip.duration if mid_clip else 0.0

        mid_index = len(content_clips) // 2
        first_half = content_clips[:mid_index]
        second_half = content_clips[mid_index:]

        all_clips = []
        if intro_clip:
            all_clips.append(intro_clip)
        all_clips.extend(first_half)
        if mid_clip:
            all_clips.append(mid_clip)
        all_clips.extend(second_half)
        if outro_clip:
            all_clips.append(outro_clip)

        if progress_callback:
            progress_callback("🔗 Concatenating clips (audio travels with each clip)...")

        # concatenate_videoclips also concatenates each clip's audio, producing a
        # single continuous track in which exactly one source is audible at any
        # moment — no CompositeAudioClip, no overlap, no lip-sync drift.
        final_video = concatenate_videoclips(all_clips, method="compose")

        # --- Apply text overlays BEFORE title card ---
        if enable_text_overlays:
            text_overlays = script.get("text_overlays", [])
            if text_overlays and progress_callback:
                progress_callback(f"📝 Adding {len(text_overlays)} text overlay(s)...")

            for overlay in text_overlays:
                text = overlay.get("text", "")
                position = overlay.get("position", "intro")

                if position == "intro":
                    start_time = intro_duration + 2.0
                elif position == "mid":
                    # Show 2s after mid-avatar ends
                    start_time = intro_duration + sum(c.duration for c in first_half) + mid_duration + 2.0
                else:
                    start_time = intro_duration + 2.0

                # Clamp to valid range
                start_time = min(start_time, max(0, final_video.duration - 5.0))

                final_video = apply_text_overlay(
                    video_clip=final_video,
                    text=text,
                    start_time=start_time,
                    duration=4.0,
                    position="bottom",
                    font_size=36,
                )

        # --- Apply logo watermark over the full video ---
        if logo_path and os.path.exists(logo_path):
            if progress_callback:
                progress_callback(f"🏷️ Applying logo watermark ({logo_position})...")
            final_video = apply_logo_watermark(
                video_clip=final_video,
                logo_path=logo_path,
                position=logo_position,
                opacity=logo_opacity,
            )

        # --- Add title card LAST (after overlays/logo, so it's clean) ---
        # NOTE: FadeOut is NOT applied here. It is applied globally AFTER
        # the title card so the full video ends with a single clean fade-to-black.
        if enable_title_card:
            card_title = title_card_title or script.get("title", "")
            card_subtitle = title_card_subtitle or ""

            if card_title or card_subtitle or (logo_path and os.path.exists(logo_path)):
                if progress_callback:
                    progress_callback("🎬 Generating title card...")

                title_card_path = generate_title_card(
                    logo_path=logo_path,
                    title=card_title,
                    subtitle=card_subtitle,
                    duration=5.0,
                    size=final_video.size,
                )

                if title_card_path and os.path.exists(title_card_path):
                    try:
                        title_clip = VideoFileClip(title_card_path)
                        all_opened_clips.append(title_clip)

                        # If the avatar outro was unavailable, speak the outro
                        # narration OVER the title card so the video still ends
                        # with a spoken conclusion. The narration becomes the title
                        # card's OWN audio, so it remains the only voice playing.
                        if (
                            outro_clip is None
                            and outro_narration_result
                            and outro_narration_result.get("status") == "completed"
                            and outro_narration_result.get("file_path")
                            and os.path.exists(outro_narration_result["file_path"])
                        ):
                            try:
                                outro_narr_audio = AudioFileClip(
                                    outro_narration_result["file_path"]
                                )
                                all_opened_clips.append(outro_narr_audio)
                                if outro_narr_audio.duration > title_clip.duration:
                                    outro_narr_audio = outro_narr_audio.subclipped(
                                        0, title_clip.duration
                                    )
                                title_clip = title_clip.with_audio(outro_narr_audio)
                                if progress_callback:
                                    progress_callback(
                                        f"🎙️ Outro narration set on title card "
                                        f"({outro_narr_audio.duration:.1f}s)"
                                    )
                            except Exception as e:
                                if progress_callback:
                                    progress_callback(
                                        f"⚠️ Outro narration on title card failed: {e}"
                                    )

                        final_video = concatenate_videoclips(
                            [final_video, title_clip], method="compose"
                        )
                        if progress_callback:
                            progress_callback("✅ Title card added (5s)")
                    except Exception as e:
                        if progress_callback:
                            progress_callback(f"⚠️ Title card failed: {e}")

        # --- Apply global FadeIn (start) and FadeOut (end) to the COMPLETE video ---
        # FadeIn: video opens from black (professional opening)
        # FadeOut: video closes to black after the title card (clean ending, not abrupt)
        final_video = final_video.with_effects([vfx.FadeIn(0.5), vfx.FadeOut(2.0)])

        # --- Export final video with quality-controlled encoding ---
        if progress_callback:
            progress_callback("💾 Exporting final video (high-quality H.264/AAC)...")

        title = script.get("title", "generated_video")
        safe_title = "".join(c if c.isalnum() or c in "._- " else "_" for c in title)[:50]
        output_path = os.path.join(OUTPUT_DIR, f"{safe_title}.mp4")

        final_video.write_videofile(
            output_path,
            codec="libx264",
            audio_codec="aac",
            # 25fps matches the Azure Avatar render rate exactly.
            # This preserves EVERY mouth-animation frame without drops.
            # Sora content (~30fps) adapts cleanly (slight frame skip in
            # natural motion is invisible; frame DROPS in lip animation are not).
            fps=25,
            preset="slow",              # Better compression quality
            ffmpeg_params=[
                "-crf", "18",           # High visual quality (0=lossless, 23=default, 18=near-lossless)
                "-pix_fmt", "yuv420p",  # Maximum compatibility
                "-movflags", "+faststart",  # Web-optimized (moov atom at front)
            ],
            audio_bitrate="192k",       # Broadcast-quality audio
            logger=None,
        )

        # All clips and audio (avatar, content, narration, title) are tracked in
        # all_opened_clips; close them now that the write has completed.
        _safe_close_all()

        # Read final duration without leaving a dangling file handle
        final_duration = 0.0
        try:
            check_clip = VideoFileClip(output_path)
            final_duration = check_clip.duration
            check_clip.close()
        except Exception:
            pass

        if progress_callback:
            progress_callback(
                f"✅ Video assembled: {final_duration:.1f}s ({final_duration / 60:.1f} min)"
            )

        return {
            "status": "completed",
            "file_path": output_path,
            "duration": final_duration,
            "error": None,
        }

    except Exception as e:
        _safe_close_all()
        logger.exception("Video assembly failed")
        return {
            "status": "failed",
            "file_path": None,
            "duration": 0,
            "error": f"Assembly failed: {str(e)}",
        }


def create_placeholder_video(
    duration_seconds: int = 5,
    size: tuple = (1280, 720),
    text: str = "Generating...",
) -> str:
    """
    Create a simple placeholder video clip (solid color with text).
    Used as fallback when a Sora scene fails to generate.
    """
    output_path = os.path.join(OUTPUT_DIR, f"placeholder_{duration_seconds}s.mp4")

    clip = ColorClip(size=size, color=(30, 30, 50), duration=duration_seconds)
    # moviepy v2: use with_fps() instead of set_fps()
    clip = clip.with_fps(25)
    clip.write_videofile(output_path, codec="libx264", logger=None)
    clip.close()

    return output_path
