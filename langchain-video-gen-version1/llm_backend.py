"""
llm_backend.py — GPT-based script generation for video content.
Uses AzureAIOpenAIApiChatModel to analyze uploaded content and generate
structured video scripts with scenes, narration, and visual descriptions.
Generic — works for any topic, brand, or content type.
"""

import os
import json
import math
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from langchain_azure_ai.chat_models import AzureAIOpenAIApiChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from video_styles import build_style_guidance, build_scene_prompt_template

load_dotenv()

# --- Model Setup ---
credential = DefaultAzureCredential()

model = AzureAIOpenAIApiChatModel(
    project_endpoint=os.environ["AZURE_AI_PROJECT_ENDPOINT"],
    credential=credential,
    model=os.environ.get("MODEL_DEPLOYMENT_NAME", "gpt-5.2"),
    temperature=0.7,
    stream_usage=True,
)

# --- System Prompts ---
SCRIPT_GENERATION_PROMPT = """You are a professional video script writer with deep expertise in Sora 2 video generation prompts. Given source content and user instructions, create a structured video script.

The video must be approximately {duration_minutes} minute(s) long ({total_seconds} seconds).
Create exactly {scene_count} scenes. Scenes 1 through {scene_count_minus_one} are 12 seconds each. Scene {scene_count} (the final scene) is {last_scene_duration} seconds.

{style_guidance}

OUTPUT FORMAT — Return ONLY valid JSON with this exact structure:
{{
    "title": "Video title",
    "intro_narration": "A warm 1-2 sentence opening that the avatar host says. Keep under 20 words.",
    "mid_narration": "A 1-2 sentence mid-video bridge from the avatar. Keep under 20 words.",
    "outro_narration": "A warm 1-2 sentence closing with optional call to action. Keep under 30 words.",
    "text_overlays": [
        {{"text": "Short impactful opening tagline", "position": "intro"}},
        {{"text": "Short impactful mid-section tagline", "position": "mid"}}
    ],
    "scenes": [
        {{
            "scene_number": 1,
            "duration_seconds": 12,
            "visual_description": "Detailed Sora 2-ready visual prompt. See SORA 2 RULES below.",
            "narration_text": "Words spoken as voiceover for this scene."
        }}
    ],
    "total_duration_seconds": {total_seconds}
}}

SCENE DURATION RULES (CRITICAL):
- Scenes 1 through {scene_count_minus_one}: set duration_seconds = 12
- Scene {scene_count} (final scene): set duration_seconds = {last_scene_duration}
- Do NOT set any scene to duration_seconds > 12 (Sora 2 hard limit).

NARRATION PACING PER SCENE:
- 12-second scene: write narration_text of approximately 20-24 words (≈2 words/second)
- 8-second scene: write narration_text of approximately 14-18 words
- 4-second scene: write narration_text of approximately 6-10 words
- Keep narration natural and unhurried. Never cram more than 2.5 words/second.

SORA 2 VISUAL_DESCRIPTION RULES (CRITICAL — follow OpenAI's official Sora 2 prompting guide):
- Be specific about visible results, not vague feelings. Instead of "beautiful street" → "wet asphalt, zebra crosswalk, neon signs reflecting in puddles".
- Describe ONE camera setup, ONE subject action, ONE lighting recipe per scene.
- Describe action in beats: "takes four steps to the window, pauses, pulls curtain in the final second".
- Name 3-5 color anchors per scene to keep palette stable.
- Specify camera framing (wide/medium/close-up), angle (eye level/low/high), and motion (locked-off/dolly/slow push-in).
- Name the lens and DOF when relevant (e.g., "35mm, shallow depth of field").
- Describe lighting quality and direction (e.g., "soft window key, cool rim from hallway").
- Avoid signage, logos, or trademarked branding in scene descriptions.
- Keep visual_description under 200 words but rich in concrete detail.
- Always write visual_description in ENGLISH (Sora 2 requirement).
- Maintain character/subject consistency: if a person appears in multiple scenes, describe them identically each time (hair color, clothing, posture).

NARRATION RULES:
- narration_text MUST be written in {language_name}. No special characters.
- Pace: ~2 words per second of scene duration (see NARRATION PACING above).
- intro_narration, mid_narration, outro_narration: write in {language_name}.
- text_overlays: write in {language_name}, each under 6 words.

GENERAL RULES:
- Ensure total scene durations sum to approximately {total_seconds} seconds.
- Video flows logically: introduction → body → conclusion.
- If images were provided, incorporate their visual themes.
- Do NOT include avatar/intro/outro scenes in the scenes array — those are handled separately.
- Adapt tone, style, and content to match the user's prompt and selected category."""

SCENE_ENHANCE_PROMPT = """You are a Sora 2 visual prompt engineer. Take this scene description and produce an optimized Sora 2 prompt using the official structured format.

FORMAT (use exactly these sections):
Style: [aesthetic, film stock, color grade, texture]

[Prose scene description — setting, subjects, action in concrete visual terms]

Cinematography:
Camera: [framing + angle + motion]
Lens: [focal length and DOF]
Lighting: [quality + direction + color temperature]
Palette anchors: [3-5 specific colors]
Mood: [tone]

Actions:
- [Beat 1: specific gesture/movement]
- [Beat 2: specific gesture/movement]
- [Beat 3 if needed]

Background Sound:
[Diegetic ambience cues only]

RULES:
- Use concrete visual nouns and verbs ("wet asphalt" not "beautiful street").
- One camera move, one action focus per scene.
- Keep total under 200 words.
- No text/signage/logos in the scene.
- Do not include dialogue or written words inside the visual.

Scene description: {description}
Scene narration context: {narration}

Return ONLY the formatted Sora 2 prompt, nothing else."""


def generate_video_script(
    text_content: str,
    image_descriptions: list,
    prompt: str,
    duration_minutes: float = 1,
    language: str = "english",
    category: str = "Auto (LLM decides)",
) -> dict:
    """
    Generate a structured video script from content + user prompt.

    Args:
        text_content: Extracted text from uploaded files
        image_descriptions: List of image description strings
        prompt: User's additional instructions/prompt
        duration_minutes: Target video length in minutes
        language: Target language for narration
        category: Video category preset name (e.g., "Cinematic", "Educational")

    Returns:
        Parsed JSON script with scenes
    """
    total_seconds = int(duration_minutes * 60)
    # Use ceiling division so scenes fill the full requested duration.
    # e.g. 90s → ceil(90/12) = 8 scenes (7×12s + 1×6s = 90s)
    scene_count = max(2, math.ceil(total_seconds / 12))

    # Calculate per-scene durations: all 12s except the last which fills the remainder
    last_scene_duration = total_seconds - (scene_count - 1) * 12
    # Snap last scene to valid Sora 2 durations: 4, 8, or 12
    if last_scene_duration <= 4:
        last_scene_duration = 4
    elif last_scene_duration <= 8:
        last_scene_duration = 8
    else:
        last_scene_duration = 12
    # Recompute actual total with snapped last duration
    actual_total = (scene_count - 1) * 12 + last_scene_duration

    # Language display names
    language_names = {
        "english": "English",
        "hindi": "Hindi",
        "telugu": "Telugu",
        "kannada": "Kannada",
        "tamil": "Tamil",
    }
    language_name = language_names.get(language, "English")

    # Build category-specific style guidance
    style_guidance = build_style_guidance(category)

    system_prompt = SCRIPT_GENERATION_PROMPT.format(
        duration_minutes=round(duration_minutes, 2),
        scene_count=scene_count,
        scene_count_minus_one=max(1, scene_count - 1),
        total_seconds=actual_total,
        language_name=language_name,
        style_guidance=style_guidance if style_guidance else "VIDEO CATEGORY: Auto — use your best judgment based on the user's prompt.\n",
        last_scene_duration=last_scene_duration,
    )

    # Build user message with all context
    user_parts = []

    if text_content:
        user_parts.append(f"=== SOURCE DOCUMENT CONTENT ===\n{text_content}")

    if image_descriptions:
        user_parts.append(
            f"=== UPLOADED IMAGES ===\n"
            + "\n".join(f"- Image {i+1}: {desc}" for i, desc in enumerate(image_descriptions))
        )

    user_parts.append(f"=== USER INSTRUCTIONS ===\n{prompt}")
    user_parts.append(
        f"\nGenerate a {duration_minutes}-minute video script with ~{scene_count} scenes. "
        f"Return ONLY valid JSON."
    )

    user_message = "\n\n".join(user_parts)

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_message),
    ]

    response = model.invoke(messages)

    # Extract text from response — handle both string and content block list formats
    if isinstance(response.content, str):
        raw = response.content
    elif isinstance(response.content, list):
        # Content blocks: [{'type': 'text', 'text': '...'}, ...]
        raw = "".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in response.content
        )
    else:
        raw = str(response.content)

    # Parse JSON from response (handle markdown code blocks)
    raw = raw.strip()
    if raw.startswith("```json"):
        raw = raw[7:]
    elif raw.startswith("```"):
        raw = raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]
    raw = raw.strip()

    try:
        script = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse video script JSON: {e}\nRaw response: {raw[:500]}")

    return script


def enhance_scene_prompt(description: str, narration: str) -> str:
    """
    Enhance a scene's visual description into an optimized Sora 2 prompt.
    """
    messages = [
        SystemMessage(content="You are a visual prompt engineer for AI video generation."),
        HumanMessage(
            content=SCENE_ENHANCE_PROMPT.format(
                description=description, narration=narration
            )
        ),
    ]

    response = model.invoke(messages)
    if isinstance(response.content, str):
        return response.content
    elif isinstance(response.content, list):
        return "".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in response.content
        )
    return str(response.content)


def describe_images(image_data: list) -> list:
    """
    Use GPT vision to describe uploaded images for script context.

    Args:
        image_data: List of (base64_str, mime_type, filename)

    Returns:
        List of description strings
    """
    descriptions = []

    for b64, mime, filename in image_data:
        content_parts = [
            {"type": "text", "text": "Describe this image in detail for use as context in a video script. "
             "Focus on: subjects, colors, mood, setting, and any text visible."},
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
        ]

        messages = [HumanMessage(content=content_parts)]

        try:
            response = model.invoke(messages)
            if isinstance(response.content, str):
                desc = response.content
            elif isinstance(response.content, list):
                desc = "".join(
                    block.get("text", "") if isinstance(block, dict) else str(block)
                    for block in response.content
                )
            else:
                desc = str(response.content)
            descriptions.append(f"[{filename}]: {desc}")
        except Exception as e:
            descriptions.append(f"[{filename}]: (Could not analyze image: {e})")

    return descriptions
