"""
overlay_engine.py — Logo watermark, text overlays, and title card generation.
Applies persistent branding elements on top of the assembled video.
"""

import os
import tempfile
from PIL import Image, ImageDraw, ImageFont
import numpy as np
from moviepy import (
    VideoFileClip,
    ImageClip,
    TextClip,
    CompositeVideoClip,
    ColorClip,
    concatenate_videoclips,
    vfx,
)


# Default logo position options
LOGO_POSITIONS = {
    "top-right": lambda logo_size, video_size: (video_size[0] - logo_size[0] - 20, 20),
    "top-left": lambda logo_size, video_size: (20, 20),
    "bottom-right": lambda logo_size, video_size: (video_size[0] - logo_size[0] - 20, video_size[1] - logo_size[1] - 20),
    "bottom-left": lambda logo_size, video_size: (20, video_size[1] - logo_size[1] - 20),
}


def apply_logo_watermark(
    video_clip,
    logo_path: str,
    position: str = "top-right",
    opacity: float = 0.7,
    scale: float = 0.12,
) -> "CompositeVideoClip":
    """
    Apply a persistent logo watermark on the video.

    Args:
        video_clip: MoviePy video clip
        logo_path: Path to the logo image file (PNG with transparency preferred)
        position: One of 'top-right', 'top-left', 'bottom-right', 'bottom-left'
        opacity: Logo opacity (0.0 to 1.0)
        scale: Logo size relative to video width

    Returns:
        CompositeVideoClip with logo overlay
    """
    if not logo_path or not os.path.exists(logo_path):
        return video_clip

    try:
        # Load and resize logo
        logo_img = Image.open(logo_path).convert("RGBA")

        # Scale logo relative to video width
        video_w, video_h = video_clip.size
        target_width = int(video_w * scale)
        aspect = logo_img.height / logo_img.width
        target_height = int(target_width * aspect)
        logo_img = logo_img.resize((target_width, target_height), Image.LANCZOS)

        # Apply opacity
        if opacity < 1.0:
            alpha = logo_img.split()[3]
            alpha = alpha.point(lambda p: int(p * opacity))
            logo_img.putalpha(alpha)

        # Convert to numpy array for moviepy
        logo_array = np.array(logo_img)

        # Create ImageClip with transparency
        logo_clip = (
            ImageClip(logo_array)
            .with_duration(video_clip.duration)
        )

        # Calculate position
        pos_func = LOGO_POSITIONS.get(position, LOGO_POSITIONS["top-right"])
        pos = pos_func((target_width, target_height), (video_w, video_h))

        logo_clip = logo_clip.with_position(pos)

        return CompositeVideoClip([video_clip, logo_clip])

    except Exception as e:
        print(f"⚠️ Logo watermark failed: {e}")
        return video_clip


def apply_text_overlay(
    video_clip,
    text: str,
    start_time: float,
    duration: float = 4.0,
    position: str = "center",
    font_size: int = 40,
    color: str = "white",
    bg_opacity: float = 0.5,
) -> "CompositeVideoClip":
    """
    Apply a text overlay on the video at a specific time.

    Args:
        video_clip: MoviePy video clip
        text: Text to display
        start_time: When to show the text (seconds)
        duration: How long to show (seconds)
        position: Position ('center', 'bottom', 'top')
        font_size: Font size
        color: Text color
        bg_opacity: Background overlay opacity

    Returns:
        CompositeVideoClip with text overlay
    """
    if not text:
        return video_clip

    try:
        video_w, video_h = video_clip.size

        # Create text using PIL (more reliable than TextClip with fonts)
        text_img = _create_text_image(
            text=text,
            max_width=int(video_w * 0.8),
            font_size=font_size,
            color=color,
            bg_opacity=bg_opacity,
        )

        text_clip = (
            ImageClip(text_img)
            .with_duration(duration)
            .with_start(start_time)
            .with_effects([vfx.FadeIn(0.5), vfx.FadeOut(0.5)])
        )

        # Position
        if position == "center":
            text_clip = text_clip.with_position("center")
        elif position == "bottom":
            text_clip = text_clip.with_position(("center", video_h - text_img.shape[0] - 60))
        elif position == "top":
            text_clip = text_clip.with_position(("center", 60))

        return CompositeVideoClip([video_clip, text_clip])

    except Exception as e:
        print(f"⚠️ Text overlay failed: {e}")
        return video_clip


def _create_text_image(
    text: str,
    max_width: int = 800,
    font_size: int = 40,
    color: str = "white",
    bg_opacity: float = 0.5,
) -> np.ndarray:
    """Create a text image with semi-transparent background using PIL."""
    # Try to find a good font
    font = None
    font_paths = [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFNSDisplay.ttf",
        "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                font = ImageFont.truetype(fp, font_size)
                break
            except Exception:
                continue
    if font is None:
        font = ImageFont.load_default()

    # Calculate text size
    dummy_img = Image.new("RGBA", (1, 1))
    draw = ImageDraw.Draw(dummy_img)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    # Add padding
    padding = 20
    img_w = min(text_w + padding * 2, max_width + padding * 2)
    img_h = text_h + padding * 2

    # Create image with semi-transparent background
    bg_alpha = int(255 * bg_opacity)
    img = Image.new("RGBA", (img_w, img_h), (0, 0, 0, bg_alpha))
    draw = ImageDraw.Draw(img)

    # Draw text centered
    text_x = (img_w - text_w) // 2
    text_y = (img_h - text_h) // 2
    draw.text((text_x, text_y), text, font=font, fill=color)

    return np.array(img)


def generate_title_card(
    logo_path: str = None,
    title: str = "",
    subtitle: str = "",
    duration: float = 5.0,
    size: tuple = (1280, 720),
    bg_color: tuple = (30, 30, 35),
) -> str:
    """
    Generate a title card frame (logo + text on dark background).

    Args:
        logo_path: Path to logo image
        title: Main title text
        subtitle: Subtitle text (e.g., "Luxury Interior Experiences")
        duration: Duration of the title card in seconds
        size: Video size (width, height)
        bg_color: Background color RGB tuple

    Returns:
        Path to generated title card video file
    """
    try:
        video_w, video_h = size

        # Create background
        img = Image.new("RGBA", (video_w, video_h), (*bg_color, 255))
        draw = ImageDraw.Draw(img)

        # Load fonts
        title_font = None
        subtitle_font = None
        font_paths = [
            "/System/Library/Fonts/Helvetica.ttc",
            "/System/Library/Fonts/SFNSDisplay.ttf",
            "/Library/Fonts/Arial.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
        ]
        for fp in font_paths:
            if os.path.exists(fp):
                try:
                    title_font = ImageFont.truetype(fp, 56)
                    subtitle_font = ImageFont.truetype(fp, 28)
                    break
                except Exception:
                    continue
        if title_font is None:
            title_font = ImageFont.load_default()
            subtitle_font = ImageFont.load_default()

        # Position elements vertically centered
        y_cursor = video_h // 2

        # Add logo if provided
        if logo_path and os.path.exists(logo_path):
            logo_img = Image.open(logo_path).convert("RGBA")
            # Scale logo to fit (max 30% of video height)
            max_logo_h = int(video_h * 0.3)
            max_logo_w = int(video_w * 0.4)
            logo_aspect = logo_img.width / logo_img.height
            if logo_img.height > max_logo_h:
                logo_img = logo_img.resize((int(max_logo_h * logo_aspect), max_logo_h), Image.LANCZOS)
            if logo_img.width > max_logo_w:
                logo_img = logo_img.resize((max_logo_w, int(max_logo_w / logo_aspect)), Image.LANCZOS)

            logo_x = (video_w - logo_img.width) // 2
            logo_y = (video_h - logo_img.height) // 2 - 60
            img.paste(logo_img, (logo_x, logo_y), logo_img)
            y_cursor = logo_y + logo_img.height + 30

        # Add title
        if title:
            bbox = draw.textbbox((0, 0), title, font=title_font)
            tw = bbox[2] - bbox[0]
            draw.text(((video_w - tw) // 2, y_cursor), title, font=title_font, fill=(255, 220, 180))
            y_cursor += 70

        # Add subtitle
        if subtitle:
            bbox = draw.textbbox((0, 0), subtitle, font=subtitle_font)
            sw = bbox[2] - bbox[0]
            draw.text(((video_w - sw) // 2, y_cursor), subtitle, font=subtitle_font, fill=(200, 200, 200))

        # Convert to numpy and create video clip
        frame = np.array(img.convert("RGB"))
        clip = ImageClip(frame).with_duration(duration).with_effects([vfx.FadeIn(1.0), vfx.FadeOut(1.5)])

        # Export to temp file
        output_path = os.path.join(tempfile.mkdtemp(), "title_card.mp4")
        clip.write_videofile(output_path, codec="libx264", fps=24, logger=None)
        clip.close()

        return output_path

    except Exception as e:
        print(f"⚠️ Title card generation failed: {e}")
        return None
