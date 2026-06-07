"""
app.py — Gradio UI for AI Video Generator with Sora 2 + Avatar Presenter.
Upload files (PDF, PPTX, Word, images) + provide a prompt → generates a narrated video
with an AI avatar presenter and multi-language support.
Supports: optional logo watermark, text overlays, title card, multi-point avatar.
Options: voice (male/female), duration (auto or manual), language, avatar, logo, overlays.
"""

import os
import shutil
import gradio as gr
from dotenv import load_dotenv

load_dotenv()

from content_extractor import extract_content
from llm_backend import generate_video_script, describe_images, enhance_scene_prompt
from video_engine import generate_all_scenes, get_resolution_choices, get_resolution_value
from tts_engine import generate_per_scene_narration, generate_narration
from video_assembler import assemble_video
from avatar_engine import generate_intro_and_outro, get_avatar_choices, AVATAR_CATALOG
from video_styles import get_category_names, build_scene_prompt_template


# ─── State ───────────────────────────────────────────────────────────────────
generation_log = []

# Logo is fully optional — only used if user uploads one
DEFAULT_LOGO_PATH = None


def log_status(msg: str):
    """Append to generation log."""
    generation_log.append(msg)


def _detect_duration_from_prompt(prompt: str):
    """
    Auto-detect video duration from the prompt text.
    Looks for patterns like '60 seconds', '2 minutes', '90s', '1-minute', etc.
    Returns duration in seconds, or None if no duration is found in the prompt.
    """
    import re
    prompt_lower = prompt.lower()

    # Match patterns like "60 seconds", "60-second", "60s"
    sec_match = re.search(r'(\d+)\s*[-]?\s*(?:seconds?|sec|s\b)', prompt_lower)
    if sec_match:
        return min(max(int(sec_match.group(1)), 10), 300)

    # Match patterns like "2 minutes", "2-minute", "2 min"
    min_match = re.search(r'(\d+(?:\.\d+)?)\s*[-]?\s*(?:minutes?|min|m\b)', prompt_lower)
    if min_match:
        return min(max(int(float(min_match.group(1)) * 60), 10), 300)

    return None  # No duration found in prompt


def filter_avatars_by_voice(voice: str):
    """Return avatar choices filtered by selected voice gender."""
    gender = "female" if "female" in voice.lower() else "male"
    filtered = [name for name, cfg in AVATAR_CATALOG.items() if cfg["gender"] == gender]
    default = filtered[0] if filtered else get_avatar_choices()[0]
    return gr.update(choices=filtered, value=default)


def toggle_avatar_controls(use_avatar: str):
    """Show or hide the avatar dropdown based on the user's avatar toggle."""
    visible = (use_avatar == "Use Avatar")
    return gr.update(visible=visible)


# ─── Main Pipeline ───────────────────────────────────────────────────────────
def generate_video(
    files,
    prompt: str,
    duration: int,
    voice: str,
    language: str,
    resolution: str,
    category: str,
    use_avatar: str,
    avatar: str,
    logo_file,
    logo_position: str,
    logo_opacity: float,
    enable_text_overlays: bool,
    enable_title_card: bool,
    title_card_title: str,
    title_card_subtitle: str,
):
    """
    Full video generation pipeline (generator — yields live updates to GUI).
    1. Extract content from uploaded files
    2. Generate video script (GPT) in selected language
    3. Generate avatar segments (intro + mid + outro)
    4. Generate video clips (Sora 2)
    5. Generate narration (TTS) in selected language
    6. Assemble final video with overlays, watermark, and title card
    """
    generation_log.clear()

    if not prompt or not prompt.strip():
        yield None, "❌ Please provide a prompt describing what video you want.", ""
        return

    # Resolve logo path — only if user uploaded one (logo is optional)
    logo_path = None
    if logo_file:
        logo_path = os.path.join(os.path.dirname(__file__), "assets", "uploaded_logo.png")
        os.makedirs(os.path.dirname(logo_path), exist_ok=True)
        shutil.copy2(logo_file, logo_path)

    # Parse duration: PROMPT takes highest priority, then GUI slider, then 60s default
    prompt_duration = _detect_duration_from_prompt(prompt)
    if prompt_duration is not None:
        # Prompt explicitly contains a duration — always use it
        total_seconds = prompt_duration
    elif duration and int(duration) > 0:
        # GUI slider set (and prompt has no duration) — use slider value
        total_seconds = int(duration)
    else:
        total_seconds = 60  # Final default
    duration_minutes = total_seconds / 60

    # Parse voice
    voice_gender = "female" if "female" in voice.lower() else "male"

    # Parse language
    language_map = {
        "English": "english",
        "Hindi (हिन्दी)": "hindi",
        "Telugu (తెలుగు)": "telugu",
        "Kannada (ಕನ್ನಡ)": "kannada",
        "Tamil (தமிழ்)": "tamil",
    }
    language_key = language_map.get(language, "english")

    status_updates = []

    def update_status(msg):
        status_updates.append(msg)
        log_status(msg)

    def current_log():
        return "\n".join(status_updates)

    # ─── Step 1: Extract content from files ─────────────────────────────
    update_status("📄 Step 1/6: Extracting content from uploaded files...")
    yield None, "⏳ Step 1/6: Extracting content...", current_log()

    text_content = ""
    image_data = []
    file_names = []

    if files:
        file_paths = [f.name if hasattr(f, 'name') else f for f in files]
        extracted = extract_content(file_paths)
        text_content = extracted["text_content"]
        image_data = extracted["image_data"]
        file_names = extracted["file_names"]
        update_status(f"   ✅ {extracted['summary']} — {', '.join(file_names)}")
    else:
        update_status("   ℹ️ No files uploaded — generating from prompt only")

    yield None, "⏳ Step 1/6: Content extracted", current_log()

    # ─── Step 2: Describe images (if any) ───────────────────────────────
    image_descriptions = []
    if image_data:
        update_status("🖼️ Analyzing uploaded images...")
        yield None, "⏳ Analyzing images...", current_log()
        image_descriptions = describe_images(image_data)
        update_status(f"   ✅ {len(image_descriptions)} image(s) analyzed")
        yield None, "⏳ Images analyzed", current_log()

    # ─── Step 3: Generate video script ──────────────────────────────────
    update_status(f"📝 Step 2/6: Generating {total_seconds}s video script in {language}...")
    yield None, f"⏳ Step 2/6: Generating script ({language}, {total_seconds}s)...", current_log()

    try:
        script = generate_video_script(
            text_content=text_content,
            image_descriptions=image_descriptions,
            prompt=prompt,
            duration_minutes=duration_minutes,
            language=language_key,
            category=category,
        )
        scene_count = len(script.get("scenes", []))
        # Estimate time: ~2-4 min per Sora 2 clip
        est_minutes = scene_count * 3
        update_status(
            f"   ✅ Script: \"{script.get('title', 'Untitled')}\" — {scene_count} scenes\n"
            f"   ⏱️ Estimated Sora 2 time: ~{est_minutes} min ({scene_count} clips × ~3 min each)"
        )
    except Exception as e:
        error_msg = f"❌ Script generation failed: {str(e)}"
        update_status(error_msg)
        yield None, error_msg, current_log()
        return

    yield None, f"⏳ Script ready ({scene_count} scenes). Generating video...", current_log()

    # ─── Step 4: Generate avatar intro & outro (or skip) ───────────────
    want_avatar = (use_avatar == "Use Avatar")

    if want_avatar:
        update_status(f"🧑‍💼 Step 3/6: Generating AI avatar presenter ({language})...")
        yield None, f"⏳ Step 3/6: Avatar presenter ({language})...", current_log()

        avatar_segments = generate_intro_and_outro(
            script=script,
            language=language_key,
            voice_gender=voice_gender,
            avatar_name=avatar,
            progress_callback=update_status,
        )

        intro_ok = avatar_segments.get("intro", {}).get("status") == "completed"
        mid_ok   = avatar_segments.get("mid",   {}).get("status") == "completed"
        outro_ok = avatar_segments.get("outro", {}).get("status") == "completed"
        update_status(
            f"   📊 Avatar: intro {'✅' if intro_ok else '⚠️ skipped'}, "
            f"mid {'✅' if mid_ok else '⚠️ skipped'}, "
            f"outro {'✅' if outro_ok else '⚠️ skipped'}"
        )
        yield None, "⏳ Avatar done. Generating Sora 2 clips (this takes a while)...", current_log()
    else:
        # User explicitly opted out — skip avatar entirely
        avatar_segments = {
            "intro": {"status": "skipped", "file_path": None, "duration_estimate": 0, "error": None},
            "mid":   {"status": "skipped", "file_path": None, "duration_estimate": 0, "error": None},
            "outro": {"status": "skipped", "file_path": None, "duration_estimate": 0, "error": None},
        }
        intro_ok = mid_ok = outro_ok = False
        update_status("⏭️ Step 3/6: Avatar skipped — video will open directly with content")
        yield None, "⏳ Step 3/6: Avatar skipped. Generating Sora 2 clips...", current_log()

    # ─── Step 5: Generate video clips (Sora 2) ─────────────────────────
    update_status(f"🎬 Step 4/6: Generating {scene_count} video clips with Sora 2...")
    update_status(f"   ⏱️ Each clip takes 1-5 minutes. Please be patient...")
    yield None, f"⏳ Step 4/6: Sora 2 generating {scene_count} clips (~{est_minutes} min)...", current_log()

    # Resolve resolution from GUI selection
    video_resolution = get_resolution_value(resolution) if resolution else "1280x720"

    # Generate clips one by one with live yield updates
    from video_engine import generate_and_wait

    video_results = []
    scenes = script.get("scenes", [])
    for i, scene in enumerate(scenes):
        scene_num = scene.get("scene_number", i + 1)
        scene_prompt = scene.get("visual_description", "")
        scene_narration = scene.get("narration_text", "")
        scene_duration = scene.get("duration_seconds", 8)

        # Apply category-specific structured Sora 2 prompt format
        final_scene_prompt = build_scene_prompt_template(
            category_name=category,
            scene_description=scene_prompt,
            narration=scene_narration,
        )

        update_status(f"   🎬 Scene {scene_num}/{scene_count}: {scene_prompt[:80]}...")
        yield None, f"⏳ Sora 2: Generating scene {scene_num}/{scene_count}...", current_log()

        result = generate_and_wait(
            prompt=final_scene_prompt,
            duration_seconds=scene_duration,
            size=video_resolution,
            scene_number=scene_num,
            progress_callback=update_status,
        )
        video_results.append(result)

        if result["status"] == "completed":
            update_status(f"   ✅ Scene {scene_num}/{scene_count} complete")
        else:
            update_status(f"   ⚠️ Scene {scene_num}/{scene_count} failed: {result.get('error', 'unknown')}")

        yield None, f"⏳ Sora 2: {i+1}/{scene_count} clips done...", current_log()

    successful_clips = sum(1 for r in video_results if r["status"] == "completed")
    failed_clips = sum(1 for r in video_results if r["status"] == "failed")
    update_status(f"   📊 Video clips: {successful_clips} completed, {failed_clips} failed")

    if successful_clips == 0:
        error_msg = (
            f"❌ All video clips failed to generate. "
            f"Check your AZURE_VIDEO_ENDPOINT and AZURE_AI_API_KEY.\n"
            f"First error: {video_results[0].get('error', 'unknown') if video_results else 'no scenes'}"
        )
        update_status(error_msg)
        yield None, error_msg, current_log()
        return

    # ─── Step 6: Generate narration audio (TTS, per-scene) ─────────────
    update_status(f"🎙️ Step 5/6: Generating per-scene {voice_gender} narration in {language}...")
    yield None, f"⏳ Step 5/6: TTS narration ({language})...", current_log()

    # Generate independent TTS audio for every scene — prevents any overlap with avatar audio
    per_scene_narration = generate_per_scene_narration(
        script=script,
        voice_gender=voice_gender,
        language=language_key,
        progress_callback=update_status,
    )
    narr_ok = sum(1 for r in per_scene_narration.values() if r.get("status") == "completed")
    update_status(f"   ✅ {narr_ok}/{len(per_scene_narration)} scene narrations generated")

    # --- Outro narration fallback (plays over title card if avatar outro failed) ---
    # Guarantees the video always ends with a spoken conclusion.
    outro_narration_result = None
    if not outro_ok:
        outro_text = script.get("outro_narration", "")
        if outro_text:
            update_status("🎙️ Generating outro narration fallback (avatar outro unavailable)...")
            outro_narration_result = generate_narration(
                text=outro_text,
                voice_gender=voice_gender,
                language=language_key,
                scene_number=9999,  # Reserved slot — won't collide with content scenes
            )
            if outro_narration_result.get("status") == "completed":
                update_status("✅ Outro narration fallback ready")
            else:
                update_status(f"⚠️ Outro narration fallback failed: {outro_narration_result.get('error')}")

    yield None, "⏳ Step 6/6: Assembling final video...", current_log()

    # ─── Step 7: Assemble final video ──────────────────────────────────
    update_status("🔧 Step 6/6: Assembling final video (avatar intro → content → mid → content → outro → title card)...")

    final_result = assemble_video(
        video_clips=video_results,
        per_scene_narration=per_scene_narration,
        script=script,
        target_duration_seconds=total_seconds,
        avatar_segments=avatar_segments,
        outro_narration_result=outro_narration_result,
        logo_path=logo_path,
        logo_position=logo_position,
        logo_opacity=logo_opacity,
        enable_text_overlays=enable_text_overlays,
        enable_title_card=enable_title_card,
        title_card_title=title_card_title,
        title_card_subtitle=title_card_subtitle,
        progress_callback=update_status,
    )

    if final_result["status"] == "completed":
        duration_str = f"{final_result['duration']:.1f}s ({final_result['duration']/60:.1f} min)"
        success_msg = (
            f"✅ Video generated successfully!\n"
            f"📏 Duration: {duration_str}\n"
            f"🎬 Scenes: {successful_clips}/{scene_count}\n"
            f"🧑‍💼 Avatar: {'✅' if intro_ok else '❌'} intro / {'✅' if mid_ok else '❌'} mid / {'✅' if outro_ok else '❌'} outro\n"
            f"🎙️ Voice: {voice_gender.capitalize()} ({language})\n"
            f"🌐 Language: {language}\n"
            f"🏷️ Logo: {'✅' if logo_path else '❌'}\n"
            f"📁 File: {os.path.basename(final_result['file_path'])}"
        )
        update_status(success_msg)
        yield final_result["file_path"], success_msg, current_log()
    else:
        error_msg = f"❌ Video assembly failed: {final_result.get('error', 'unknown')}"
        update_status(error_msg)
        yield None, error_msg, current_log()


# ─── Gradio UI ───────────────────────────────────────────────────────────────
def build_ui():
    with gr.Blocks(
        title="🎬 AI Video Generator — Sora 2 + Avatar + Microsoft Foundry",
    ) as app:
        gr.Markdown(
            """
            # 🎬 AI Video Generator — Sora 2 + AI Avatar on Microsoft Foundry

            **Upload files (PDF, PPTX, Word, images) + describe your video → Get a professionally narrated video with an AI avatar presenter.**

            Video length is determined from your prompt (e.g., "create a 90-second video") or set manually via the slider.
            Logo, title card, and text overlays are all **optional**.
            """
        )

        with gr.Row():
            with gr.Column(scale=2):
                # File upload
                files_input = gr.File(
                    label="📎 Upload Files (PDF, PPTX, DOCX, Images)",
                    file_count="multiple",
                    file_types=[".pdf", ".pptx", ".ppt", ".docx", ".doc", ".txt", ".md",
                                ".png", ".jpg", ".jpeg", ".gif", ".webp"],
                    type="filepath",
                )

                # Prompt
                prompt_input = gr.Textbox(
                    label="🎯 Video Prompt",
                    placeholder="Describe the video you want. Include desired duration (e.g., 'Create a 90-second product demo video'). If no duration is specified, 60 seconds is used.",
                    lines=4,
                )

            with gr.Column(scale=1):
                # Language selection
                language_input = gr.Dropdown(
                    choices=["English", "Hindi (हिन्दी)", "Telugu (తెలుగు)", "Kannada (ಕನ್ನಡ)", "Tamil (தமிழ்)"],
                    value="English",
                    label="🌐 Language",
                )

                # Duration
                duration_input = gr.Slider(
                    minimum=0,
                    maximum=300,
                    value=0,
                    step=10,
                    label="⏱️ Video Duration (seconds) — 0 = auto-detect from prompt",
                )

                # Voice
                voice_input = gr.Radio(
                    choices=["Female Voice", "Male Voice"],
                    value="Female Voice",
                    label="🎙️ Narration Voice",
                )

                # Resolution
                resolution_input = gr.Dropdown(
                    choices=get_resolution_choices(),
                    value="1280x720 (720p Landscape)",
                    label="📐 Video Resolution",
                )

                # Video Category / Style
                category_input = gr.Dropdown(
                    choices=get_category_names(),
                    value="Cinematic",
                    label="🎨 Video Category / Style",
                    info="Choose the visual style — each preset applies Sora 2 best practices for that genre",
                )

                # Avatar toggle — explicit user choice
                use_avatar_input = gr.Radio(
                    choices=["Use Avatar", "No Avatar"],
                    value="Use Avatar",
                    label="🧑‍💼 Avatar Presenter",
                    info="'Use Avatar' — AI presenter opens and closes the video. 'No Avatar' — content only.",
                )

                # Avatar character selection — shown only when Use Avatar is selected
                female_avatars = [n for n, c in AVATAR_CATALOG.items() if c["gender"] == "female"]
                avatar_input = gr.Dropdown(
                    choices=female_avatars,
                    value=female_avatars[0] if female_avatars else None,
                    label="🎭 Choose Avatar Character",
                    visible=True,
                )

        # --- Branding & Overlays Section ---
        with gr.Accordion("🏷️ Branding & Overlays", open=True):
            with gr.Row():
                with gr.Column():
                    logo_input = gr.File(
                        label="📷 Upload Logo (optional, PNG recommended)",
                        file_count="single",
                        file_types=[".png", ".jpg", ".jpeg", ".webp"],
                        type="filepath",
                    )
                    gr.Markdown(
                        f"*Logo is optional. If not uploaded, no watermark will be applied.*"
                    )

                with gr.Column():
                    logo_position_input = gr.Dropdown(
                        choices=["top-right", "top-left", "bottom-right", "bottom-left"],
                        value="top-right",
                        label="📍 Logo Position",
                    )
                    logo_opacity_input = gr.Slider(
                        minimum=0.1,
                        maximum=1.0,
                        value=0.7,
                        step=0.1,
                        label="🔆 Logo Opacity",
                    )

            with gr.Row():
                with gr.Column():
                    enable_text_overlays_input = gr.Checkbox(
                        value=True,
                        label="📝 Enable Text Overlays",
                        info="Show text captions at key moments",
                    )
                    enable_title_card_input = gr.Checkbox(
                        value=True,
                        label="🎬 Enable Title Card",
                        info="Add branded end card with logo",
                    )

                with gr.Column():
                    title_card_title_input = gr.Textbox(
                        label="Title Card — Main Text (optional)",
                        placeholder="e.g., Your Brand Name",
                        value="",
                    )
                    title_card_subtitle_input = gr.Textbox(
                        label="Title Card — Subtitle (optional)",
                        placeholder="e.g., Your tagline here",
                        value="",
                    )

        gr.Markdown(
            "⚠️ **Sora 2 takes ~2-4 min per scene.**\n"
            "A 1-min video ≈ 5 scenes ≈ 10-20 min total generation time.\n"
            "Duration is auto-detected from your prompt, or set manually with the slider."
        )

        generate_btn = gr.Button(
            "🚀 Generate Video",
            variant="primary",
            size="lg",
        )

        # Output section
        gr.Markdown("---")

        with gr.Row():
            with gr.Column(scale=2):
                video_output = gr.Video(
                    label="🎥 Generated Video",
                    interactive=False,
                )

            with gr.Column(scale=1):
                status_output = gr.Textbox(
                    label="📊 Status",
                    lines=6,
                    interactive=False,
                )

        # Detailed log (open by default — shows live progress)
        with gr.Accordion("📋 Generation Log (live updates)", open=True):
            log_output = gr.Textbox(
                label="Full Log",
                lines=20,
                interactive=False,
            )

        # Example prompts
        gr.Markdown("---")
        gr.Markdown("### 💡 Example Prompts")
        gr.Examples(
            examples=[
                ["Create a 60-second cinematic brand film with golden-hour lighting, slow dolly moves, and warm intimate narration"],
                ["Generate a 90-second educational explainer about cloud computing — clear, bright, friendly, with clean diagrams and confident narration"],
                ["Make a 45-second product demo highlighting key features — premium commercial polish with macro details and aspirational narration"],
                ["Create a 30-second social media teaser — bold, energetic, fast cuts, punchy color, hook-driven narration"],
                ["Generate a 2-minute training tutorial walking through the steps in the uploaded document — methodical, patient, clear"],
                ["Make a 60-second documentary-style short — handheld, natural light, authentic observational tone"],
            ],
            inputs=prompt_input,
        )

        # Show/hide avatar character dropdown when the avatar toggle changes
        use_avatar_input.change(
            fn=toggle_avatar_controls,
            inputs=[use_avatar_input],
            outputs=[avatar_input],
        )

        # Filter avatar dropdown when voice changes
        voice_input.change(
            fn=filter_avatars_by_voice,
            inputs=[voice_input],
            outputs=[avatar_input],
        )

        # Wire up the generate button
        generate_btn.click(
            fn=generate_video,
            inputs=[
                files_input, prompt_input, duration_input, voice_input,
                language_input, resolution_input, category_input,
                use_avatar_input, avatar_input,
                logo_input, logo_position_input, logo_opacity_input,
                enable_text_overlays_input, enable_title_card_input,
                title_card_title_input, title_card_subtitle_input,
            ],
            outputs=[video_output, status_output, log_output],
        )

    return app


# ─── Entry Point ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = build_ui()
    app.launch(server_name="127.0.0.1", server_port=7860, share=False, theme=gr.themes.Soft())
