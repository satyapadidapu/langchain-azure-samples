"""
video_styles.py — Video category presets with Sora 2 prompt engineering best practices.

Each category provides:
- visual_style: Aesthetic guidance (film stock, grading, palette)
- cinematography: Camera setup, lens, framing, motion
- lighting: Quality, direction, mood
- pacing: How scenes should flow
- narration_tone: How the avatar/voiceover should sound
- example_palette: Color anchors for consistency

Based on the official OpenAI Sora 2 Prompting Guide (March 2026).
"""

VIDEO_CATEGORIES = {
    "Cinematic": {
        "description": "Premium film-quality storytelling — feature-film aesthetics",
        "visual_style": (
            "Shot on 35mm spherical lenses, anamorphic 2.39:1 feel, fine film grain, "
            "subtle halation on speculars, rich color grade with deep blacks and warm highlights. "
            "Filmic motion blur, shallow depth of field, organic micro-handheld imperfection."
        ),
        "cinematography": (
            "Wide establishing shots with slow dolly-in or arc moves; medium close-ups at eye level; "
            "shallow DOF isolating the subject; 32mm/50mm primes; smooth gimbal or dolly motion only."
        ),
        "lighting": (
            "Motivated practical light sources, soft key with warm tungsten fill, cool rim from window or hallway, "
            "negative fill for contrast; golden hour or dusk preferred."
        ),
        "pacing": "Deliberate and slow. Each scene breathes for 8-12 seconds.",
        "narration_tone": "Warm, intimate, reflective. Speaks in measured cadence.",
        "palette": "amber, cream, walnut brown, deep teal shadows",
        "mood": "evocative, atmospheric, cinematic",
        "sound_design": "diegetic ambience only — wind, room tone, distant city, no score in clip",
    },
    "Educational": {
        "description": "Clear teaching content — explainer-style for learning",
        "visual_style": (
            "Clean, well-lit, professional video. Crisp 4K aesthetic with neutral color grade. "
            "Minimal grain, sharp focus throughout. Modern, friendly, easy to read visual style."
        ),
        "cinematography": (
            "Steady locked-off or smooth slider shots; clear medium shots; wide overhead diagrams; "
            "occasional zoom-in on key details. 35mm equivalent lens. Deep focus to keep everything legible."
        ),
        "lighting": (
            "Soft, even three-point lighting. Bright key with subtle fill, no harsh shadows. "
            "Daylight-balanced color temperature (~5500K)."
        ),
        "pacing": "Steady and clear. 12-second scenes that allow concepts to land.",
        "narration_tone": "Clear, friendly, instructional. Conversational and confident.",
        "palette": "soft white, sky blue, light grey, accent orange",
        "mood": "clear, inviting, trustworthy",
        "sound_design": "subtle ambient room tone; no distracting background",
    },
    "Marketing / Product Demo": {
        "description": "Product showcase — premium commercial polish",
        "visual_style": (
            "Glossy commercial aesthetic. High-contrast cinematic grade with vibrant brand accents. "
            "Macro details with shallow DOF, polished surfaces, perfect reflections. Smooth slow-motion accents."
        ),
        "cinematography": (
            "Slow product rotation; macro close-ups; smooth dolly tracking; rack focus reveals; "
            "85mm-100mm lens for product hero shots; 24-35mm for lifestyle context."
        ),
        "lighting": (
            "Studio lighting with key + rim + bounce; soft gradient backdrop; controlled specular highlights; "
            "premium-looking light fall-off."
        ),
        "pacing": "Energetic but elegant. Quick cuts on product highlights, slower on lifestyle beats.",
        "narration_tone": "Confident, aspirational, polished. Bold and inviting.",
        "palette": "brand-color forward, with neutral whites and rich blacks",
        "mood": "premium, aspirational, desirable",
        "sound_design": "clean studio ambience; subtle product sound design",
    },
    "Social Media / Short-Form": {
        "description": "Snappy, attention-grabbing content for Reels/Shorts/TikTok",
        "visual_style": (
            "Bold, punchy color grade with high saturation. Vertical or square framing preferred. "
            "Dynamic, modern. Bright, eye-catching. Fast pacing."
        ),
        "cinematography": (
            "Quick whip pans, dynamic zoom-ins, hand-held energy. 24mm-35mm wide lens. "
            "Quick beats — pack the visual into 4-8 seconds per clip."
        ),
        "lighting": (
            "Bright, vibrant, high-key. Natural daylight or punchy LED. Bold, contrasty look."
        ),
        "pacing": "Fast. Short beats. 4-8 second clips with snappy transitions.",
        "narration_tone": "Energetic, casual, hook-driven. Speaks with urgency and excitement.",
        "palette": "bold, saturated, brand-forward — pop colors",
        "mood": "energetic, fun, attention-grabbing",
        "sound_design": "upbeat, punchy; clear voice over",
    },
    "Training / Tutorial": {
        "description": "Step-by-step instruction — process walkthroughs",
        "visual_style": (
            "Professional, documentary-clean look. Sharp focus, accurate colors, "
            "no artistic distortion. Visual clarity over style."
        ),
        "cinematography": (
            "Locked-off tripod shots; smooth slider moves for variety; clear over-the-shoulder POV; "
            "close-ups on hands or controls; consistent framing across steps."
        ),
        "lighting": (
            "Bright, even, daylight-balanced. No deep shadows. Practical work lighting feel."
        ),
        "pacing": "Methodical. 8-12 second scenes per step, with clear visual milestones.",
        "narration_tone": "Patient, knowledgeable, step-by-step. Speaks slowly with clarity.",
        "palette": "neutral whites, soft greys, accent color for highlights",
        "mood": "instructive, calm, methodical",
        "sound_design": "real-world process sounds (clicks, taps, machine hums) at low level",
    },
    "Documentary": {
        "description": "Authentic, observational storytelling",
        "visual_style": (
            "Handheld ENG-camera feel with mild gate weave and natural grain. 16mm-vintage texture. "
            "Natural color grade, honest skin tones, available light look."
        ),
        "cinematography": (
            "Handheld shoulder-mounted; observational wide and medium shots; natural reframing; "
            "32mm-50mm equivalent; subtle micro-handheld imperfection."
        ),
        "lighting": (
            "Available natural light. Window light + practicals. Honest, uncontrived. "
            "Color temperature varies naturally with location."
        ),
        "pacing": "Patient observational rhythm. 8-12 second scenes that linger.",
        "narration_tone": "Reflective, grounded, journalistic. First-person or observer voice.",
        "palette": "natural earth tones, honest skin, available-light hues",
        "mood": "authentic, thoughtful, observational",
        "sound_design": "natural ambience, real location audio; no score",
    },
    "Storytelling / Narrative": {
        "description": "Story-driven emotional video — like a short film",
        "visual_style": (
            "Cinematic short-film aesthetic. Rich color grade with mood-driven palettes. "
            "Carefully composed frames. Light film grain. Emotional and immersive."
        ),
        "cinematography": (
            "Mix of wide establishing, medium emotional, and intimate close-ups. "
            "Motivated camera moves — push-ins reveal emotion, pull-outs reveal context. "
            "35mm-50mm lens; shallow DOF on character moments."
        ),
        "lighting": (
            "Story-driven lighting — soft natural for tender moments, hard directional for tension. "
            "Color palette shifts to underscore emotion."
        ),
        "pacing": "Emotional rhythm. Builds and breathes — 8-12 second scenes with meaningful beats.",
        "narration_tone": "Personal, emotional, story-driven. Speaks with feeling and vulnerability.",
        "palette": "context-driven — warm for hope, cool for melancholy, contrasty for tension",
        "mood": "emotional, evocative, immersive",
        "sound_design": "subtle diegetic ambience; emotional negative space",
    },
    "Corporate / News": {
        "description": "Professional business — news-broadcast quality",
        "visual_style": (
            "Clean broadcast aesthetic. Neutral professional color grade. Sharp throughout. "
            "Corporate polish, no artistic flourish."
        ),
        "cinematography": (
            "Stable tripod and dolly shots; eye-level medium shots; clean wide establishing shots; "
            "smooth lateral slider moves; 35-50mm lens; consistent framing."
        ),
        "lighting": (
            "Bright, even three-point lighting. Daylight-balanced. Soft key with fill, subtle rim."
        ),
        "pacing": "Brisk and professional. 8-12 second scenes that deliver information efficiently.",
        "narration_tone": "Authoritative, professional, news-anchor style. Clear and credible.",
        "palette": "corporate navy, white, grey, with brand accent color",
        "mood": "credible, professional, trustworthy",
        "sound_design": "broadcast-clean room tone; no distractions",
    },
    "Auto (LLM decides)": {
        "description": "Let the AI choose the best style based on your prompt and content",
        "visual_style": "",
        "cinematography": "",
        "lighting": "",
        "pacing": "",
        "narration_tone": "",
        "palette": "",
        "mood": "",
        "sound_design": "",
    },
}


def get_category_names() -> list:
    """Return ordered list of category names for the GUI dropdown."""
    return list(VIDEO_CATEGORIES.keys())


def get_category(name: str) -> dict:
    """Return the category preset by name (empty preset if not found)."""
    return VIDEO_CATEGORIES.get(name, VIDEO_CATEGORIES["Auto (LLM decides)"])


def build_style_guidance(category_name: str) -> str:
    """
    Build a multi-line style guidance block to inject into the LLM script-generation system prompt.
    Returns an empty string for the 'Auto' category so the LLM has full creative freedom.
    """
    cat = get_category(category_name)
    if not cat.get("visual_style"):
        return ""  # Auto mode — let the LLM decide

    return (
        f"VIDEO CATEGORY: {category_name}\n"
        f"DESCRIPTION: {cat['description']}\n"
        f"\nWhen writing visual_description fields for each scene, apply these style guidelines:\n"
        f"- VISUAL STYLE: {cat['visual_style']}\n"
        f"- CINEMATOGRAPHY: {cat['cinematography']}\n"
        f"- LIGHTING: {cat['lighting']}\n"
        f"- PALETTE: {cat['palette']}\n"
        f"- MOOD: {cat['mood']}\n"
        f"- SOUND DESIGN (mention as ambience cue): {cat['sound_design']}\n"
        f"- PACING: {cat['pacing']}\n"
        f"\nWhen writing narration_text and avatar lines, use this tone: {cat['narration_tone']}\n"
    )


def build_scene_prompt_template(category_name: str, scene_description: str, narration: str) -> str:
    """
    Build a structured Sora 2 prompt using the official prompt-anatomy format
    (Style → Scene → Cinematography → Mood → Actions → Background Sound).

    Returns a fully-formatted multi-block prompt string ready to send to Sora 2.
    """
    cat = get_category(category_name)

    # Auto mode — return the LLM-enhanced scene description directly
    if not cat.get("visual_style"):
        return scene_description

    return (
        f"Style: {cat['visual_style']}\n\n"
        f"{scene_description}\n\n"
        f"Cinematography:\n"
        f"Camera: {cat['cinematography']}\n"
        f"Lighting: {cat['lighting']}\n"
        f"Palette anchors: {cat['palette']}\n"
        f"Mood: {cat['mood']}\n\n"
        f"Background Sound:\n"
        f"{cat['sound_design']}\n"
    )
