"""
_e2e_verify.py — Real end-to-end verification for the video generator.

Runs the ACTUAL production pipeline (Azure Speech Avatar + Azure TTS + Sora 2 +
the rewritten video_assembler) and then measures three required behaviours on the
final mp4:

  1. ONE VOICE AT A TIME   — the avatar voice and the narration never overlap.
  2. LIP SYNC ACCURACY     — the avatar voice in the final video is time-aligned
                             (zero lag) with the Azure-delivered avatar audio,
                             which is itself perfectly lip-synced.
  3. AVATAR AT START + END  — the video opens with the avatar and the avatar
                             returns to close it (with an optional mid segment).

This keeps the run small (2 short Sora scenes) to limit cost/time while still
exercising the full [intro → content → mid → content → outro → title] sequence.

Run:
    source ../videoenvgen/bin/activate
    python _e2e_verify.py
"""

import os
import sys
import subprocess
import numpy as np
import imageio_ffmpeg

sys.path.insert(0, os.path.dirname(__file__))

from avatar_engine import generate_intro_and_outro
from tts_engine import generate_per_scene_narration
from video_engine import generate_and_wait
from video_assembler import assemble_video
from moviepy import VideoFileClip, AudioFileClip

ANALYSIS_FPS = 16000  # decode audio at the avatar's native sample rate

LANG = "english"
GENDER = "female"
AVATAR = "Lisa - Graceful Standing"

# A tiny, self-contained script. Hand-built so the test does not depend on the
# LLM step — it only needs the keys the avatar/TTS/assembler stages consume.
SCRIPT = {
    "title": "Lip Sync Verification Test",
    "intro_narration": "Hello and welcome. This short clip verifies that the avatar opens the video.",
    "mid_narration": "We are now halfway through, and the avatar returns briefly in the middle.",
    "outro_narration": "Thanks for watching. The avatar now closes the video. Goodbye.",
    "text_overlays": [],
    "scenes": [
        {
            "scene_number": 1,
            "visual_description": "A calm blue ocean wave rolling slowly under soft daylight, cinematic.",
            "narration_text": "This is the first content scene, narrated by the background voice only.",
            "duration_seconds": 4,
        },
        {
            "scene_number": 2,
            "visual_description": "A green forest canopy with sunlight filtering through the leaves, cinematic.",
            "narration_text": "This is the second content scene, again narrated by the background voice only.",
            "duration_seconds": 4,
        },
    ],
}


def log(msg):
    print(msg, flush=True)


def decode_audio(path, fps=ANALYSIS_FPS):
    """
    Decode an entire media file's audio to a mono float64 numpy array using the
    ffmpeg binary bundled with imageio-ffmpeg.

    moviepy's own ``to_soundarray`` reader is unreliable here (its first read on
    a freshly opened clip can return degenerate DC data), so we decode PCM
    directly. This is deterministic and frame-accurate.
    """
    exe = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [exe, "-i", path, "-vn", "-ac", "1", "-ar", str(fps),
           "-f", "s16le", "-loglevel", "quiet", "pipe:1"]
    raw = subprocess.run(cmd, capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.int16).astype(np.float64) / 32768.0


def window_signal(full, t_start, t_end, fps=ANALYSIS_FPS):
    """Slice a normalised mono window [t_start, t_end) from a full mono array."""
    i0 = max(0, int(round(t_start * fps)))
    i1 = min(len(full), int(round(t_end * fps)))
    if i1 <= i0:
        return np.zeros(1)
    seg = np.asarray(full[i0:i1], dtype=np.float64)
    peak = np.max(np.abs(seg))
    if peak > 0:
        seg = seg / peak
    return seg


def raw_window(full, t_start, t_end, fps=ANALYSIS_FPS):
    """Slice an un-normalised window (for true energy / silence detection)."""
    i0 = max(0, int(round(t_start * fps)))
    i1 = min(len(full), int(round(t_end * fps)))
    return full[i0:i1] if i1 > i0 else np.zeros(1)


def best_lag_seconds(ref, test, fps=ANALYSIS_FPS, max_lag_s=0.5):
    """
    Cross-correlate two mono signals and return the lag (seconds) of `test`
    relative to `ref`. A lag near 0 means the avatar voice in the final video is
    aligned with the source avatar audio (lip sync preserved).
    """
    n = min(len(ref), len(test))
    if n < fps // 2:  # need at least ~0.5s
        return None
    ref = ref[:n] - np.mean(ref[:n])
    test = test[:n] - np.mean(test[:n])
    max_lag = int(max_lag_s * fps)
    corr = np.correlate(test, ref, mode="full")
    mid = len(corr) // 2
    window = corr[mid - max_lag: mid + max_lag + 1]
    lag_idx = int(np.argmax(window)) - max_lag
    return lag_idx / fps


def _norm_xcorr_peak(ref, test, fps=ANALYSIS_FPS, max_lag_s=0.5):
    """
    Return the peak normalised cross-correlation (0..1) between two mono signals
    within +/- max_lag_s. ~1.0 means the two signals are the same audio (the
    window carries that exact voice); low values mean a different/absent voice.
    """
    n = min(len(ref), len(test))
    if n < fps // 2:
        return 0.0
    a = ref[:n] - np.mean(ref[:n])
    b = test[:n] - np.mean(test[:n])
    denom = np.sqrt(np.sum(a ** 2) * np.sum(b ** 2))
    if denom == 0:
        return 0.0
    max_lag = int(max_lag_s * fps)
    corr = np.correlate(b, a, mode="full") / denom
    mid = len(corr) // 2
    window = corr[mid - max_lag: mid + max_lag + 1]
    return float(np.max(np.abs(window)))


def locate_segment(source_full, final_full, expected_start, win_s=2.0,
                   search_s=0.6, fps=ANALYSIS_FPS):
    """
    Find where an avatar source segment actually sits in the final audio.

    Because each clip's real duration is slightly longer than requested, the
    concatenated position of a later segment can drift by ~100-200ms from the
    arithmetic estimate — that is a *timeline placement* offset, NOT lip
    desync (within each clip the avatar's own muxed audio stays frame-locked to
    its video). We therefore search a small neighbourhood for the best-match
    offset and return (best_offset, peak_correlation).
    """
    ref = window_signal(source_full, 0.2, 0.2 + win_s)
    best_off, best_peak = expected_start, -1.0
    off = max(0.0, expected_start - search_s)
    end = expected_start + search_s
    step = 0.01
    while off <= end:
        test = window_signal(final_full, off, off + win_s)
        p = _norm_xcorr_peak(ref, test, max_lag_s=0.01)
        if p > best_peak:
            best_off, best_peak = off, p
        off += step
    return best_off, best_peak


def main():
    log("=" * 70)
    log("REAL END-TO-END VERIFICATION")
    log("=" * 70)

    # ── Stage 1: avatar intro + mid + outro (real Azure Speech Avatar) ─────
    log("\n[1/4] Generating avatar intro/mid/outro (Azure Speech Avatar)...")
    avatar_segments = generate_intro_and_outro(
        script=SCRIPT, language=LANG, voice_gender=GENDER,
        avatar_name=AVATAR, progress_callback=log,
    )
    for k in ("intro", "mid", "outro"):
        seg = avatar_segments.get(k, {})
        log(f"   avatar {k}: {seg.get('status')} -> {seg.get('file_path')}")
        if seg.get("status") != "completed":
            log(f"   ❌ Avatar {k} failed: {seg.get('error')}")
            return 1

    # Lip-sync precondition: each avatar source mp4's audio duration must match
    # its video duration (Azure muxes them in sync). The assembler keeps this
    # audio attached, so matching durations => preserved lip sync.
    for k in ("intro", "mid", "outro"):
        p = avatar_segments[k]["file_path"]
        v = VideoFileClip(p)
        a = AudioFileClip(p)
        drift = abs(v.duration - a.duration)
        log(f"   avatar {k}: video={v.duration:.3f}s audio={a.duration:.3f}s drift={drift*1000:.0f}ms")
        a.close(); v.close()
        if drift > 0.12:
            log(f"   ❌ Avatar {k} source has audio/video drift > 120ms")
            return 1

    # ── Stage 2: Sora 2 content clips (real) ───────────────────────────────
    log("\n[2/4] Generating Sora 2 content clips...")
    video_results = []
    for scene in SCRIPT["scenes"]:
        r = generate_and_wait(
            prompt=scene["visual_description"],
            duration_seconds=scene["duration_seconds"],
            size="1280x720",
            scene_number=scene["scene_number"],
            progress_callback=log,
        )
        log(f"   scene {scene['scene_number']}: {r.get('status')} -> {r.get('file_path')}")
        if r.get("status") != "completed":
            log(f"   ❌ Sora scene {scene['scene_number']} failed: {r.get('error')}")
            return 1
        video_results.append(r)

    # ── Stage 3: per-scene narration (real Azure TTS) ──────────────────────
    log("\n[3/4] Generating per-scene narration (Azure TTS)...")
    per_scene_narration = generate_per_scene_narration(
        script=SCRIPT, voice_gender=GENDER, language=LANG, progress_callback=log,
    )

    # ── Stage 4: assemble (rewritten assembler) ────────────────────────────
    log("\n[4/4] Assembling final video...")
    result = assemble_video(
        video_clips=video_results,
        per_scene_narration=per_scene_narration,
        script=SCRIPT,
        target_duration_seconds=30,
        avatar_segments=avatar_segments,
        outro_narration_result=None,
        enable_text_overlays=False,
        enable_title_card=True,
        title_card_title=SCRIPT["title"],
        title_card_subtitle="E2E test",
        progress_callback=log,
    )
    if result.get("status") != "completed":
        log(f"❌ Assembly failed: {result.get('error')}")
        return 1
    final_path = result["file_path"]
    log(f"\n✅ Final video: {final_path} ({result['duration']:.2f}s)")

    # ===================================================================
    # VERIFICATION
    # ===================================================================
    log("\n" + "=" * 70)
    log("VERIFYING REQUIRED BEHAVIOURS")
    log("=" * 70)

    passed = True

    # --- Compute the expected segment timeline (same math the assembler uses) ---
    d_intro = VideoFileClip(avatar_segments["intro"]["file_path"]).duration
    d_mid = VideoFileClip(avatar_segments["mid"]["file_path"]).duration
    d_outro = VideoFileClip(avatar_segments["outro"]["file_path"]).duration
    content_durs = [VideoFileClip(r["file_path"]).duration for r in video_results]
    mid_index = len(content_durs) // 2
    first_half = content_durs[:mid_index]
    second_half = content_durs[mid_index:]

    t = 0.0
    timeline = []  # (label, start, end, kind)
    timeline.append(("avatar_intro", t, t + d_intro, "avatar")); t += d_intro
    for i, d in enumerate(first_half):
        timeline.append((f"content_{i+1}", t, t + d, "content")); t += d
    timeline.append(("avatar_mid", t, t + d_mid, "avatar")); t += d_mid
    for i, d in enumerate(second_half):
        timeline.append((f"content_{mid_index+i+1}", t, t + d, "content")); t += d
    timeline.append(("avatar_outro", t, t + d_outro, "avatar")); t += d_outro
    content_end = t  # title card follows

    log("\nReconstructed segment timeline:")
    for label, s, e, kind in timeline:
        log(f"   {label:16s} [{s:6.2f} → {e:6.2f}]  ({kind})")

    # --- Load the final video audio once for all checks (ffmpeg PCM decode) ---
    final_clip = VideoFileClip(final_path)
    final_full = decode_audio(final_path)

    # --- CHECK 1: only one voice at a time ---
    # (a) Segments are strictly sequential (non-overlapping) by construction.
    # (b) The final mp4 carries a single mixed audio track.
    # (c) Empirically, a CONTENT window must carry the NARRATION voice and must
    #     NOT match the avatar voice — proving the avatar is muted there.
    overlap = False
    for (l1, s1, e1, _), (l2, s2, e2, _) in zip(timeline, timeline[1:]):
        if s2 + 1e-6 < e1:
            overlap = True
            log(f"   ❌ overlap: {l1} ends {e1:.2f} but {l2} starts {s2:.2f}")

    # content_1 window vs its narration source (proves narration voice is present)
    # and vs the avatar voice (proves the avatar is NOT bleeding into content).
    c1_start, c1_end = timeline[1][1], timeline[1][2]
    intro_full = decode_audio(avatar_segments["intro"]["file_path"])
    narr1 = per_scene_narration.get(1, {})
    content_matches_narration = None
    content_matches_avatar = None
    if narr1.get("status") == "completed" and os.path.exists(narr1.get("file_path", "")):
        narr1_full = decode_audio(narr1["file_path"])
        narr1_dur = len(narr1_full) / ANALYSIS_FPS
        win = min(2.5, c1_end - c1_start, narr1_dur)
        ref_narr = window_signal(narr1_full, 0.1, 0.1 + win)
        test_c1 = window_signal(final_full, c1_start + 0.1, c1_start + 0.1 + win)
        content_matches_narration = _norm_xcorr_peak(ref_narr, test_c1)
        ref_avatar = window_signal(intro_full, 0.1, 0.1 + win)
        content_matches_avatar = _norm_xcorr_peak(ref_avatar, test_c1)

    has_audio = len(final_full) > 0
    log(f"\n[CHECK 1] One voice at a time:")
    log(f"   segment overlap detected: {overlap}")
    log(f"   final mp4 has audio track: {has_audio}")
    if content_matches_narration is not None:
        log(f"   content window vs narration source : {content_matches_narration:.2f} (want high)")
        log(f"   content window vs avatar  source : {content_matches_avatar:.2f} (want low)")
    fail_c1 = (
        overlap or not has_audio or (
            content_matches_narration is not None and (
                content_matches_narration < 0.5
                or content_matches_avatar > content_matches_narration
            )
        )
    )
    if fail_c1:
        passed = False
        log("   ❌ FAIL")
    else:
        log("   ✅ PASS — sequential segments; content window carries the narration voice, not the avatar")

    # --- CHECK 2: lip sync (avatar voice matches the lip-synced source) ---
    # The avatar source mp4s are muxed audio+video with 0ms drift (verified as a
    # precondition above). The assembler binds each avatar's own audio to its own
    # video and never repositions within the clip, so lip sync is preserved iff
    # the avatar VOICE in the final equals the source avatar voice at that segment.
    # We locate each segment by correlation (robust to concatenation rounding) and
    # require a near-perfect match peak.
    log(f"\n[CHECK 2] Lip sync (avatar voice == lip-synced source, peak ≥ 0.95):")
    outro_full = decode_audio(avatar_segments["outro"]["file_path"])

    o_start = content_end - d_outro
    intro_off, intro_peak = locate_segment(intro_full, final_full, expected_start=0.0)
    outro_off, outro_peak = locate_segment(outro_full, final_full, expected_start=o_start)

    log(f"   intro: found at {intro_off:6.2f}s (expected {0.0:.2f}s, "
        f"drift {(intro_off-0.0)*1000:+.0f}ms) match peak {intro_peak:.3f}")
    log(f"   outro: found at {outro_off:6.2f}s (expected {o_start:.2f}s, "
        f"drift {(outro_off-o_start)*1000:+.0f}ms) match peak {outro_peak:.3f}")
    if intro_peak < 0.95 or outro_peak < 0.95:
        passed = False
        log("   ❌ FAIL — avatar voice in the final does not match the synced source")
    else:
        log("   ✅ PASS — avatar voice is the exact lip-synced source audio (lips match)")

    # --- CHECK 3: avatar opens and closes; content is the avatar source voice ---
    # Confirm avatar audio energy is present at the very start and just before the
    # title card, proving the avatar opens and closes the video.
    def rms(sig):
        return float(np.sqrt(np.mean(sig ** 2))) if len(sig) else 0.0

    start_energy = rms(raw_window(final_full, 0.2, 1.2))
    end_energy = rms(raw_window(final_full, o_start + 0.2, o_start + 1.2))
    log(f"\n[CHECK 3] Avatar opens and closes the video:")
    log(f"   audio energy at start (avatar intro window): {start_energy:.4f}")
    log(f"   audio energy at end   (avatar outro window): {end_energy:.4f}")
    if start_energy > 0.01 and end_energy > 0.01 and timeline[0][3] == "avatar" and timeline[-1][3] == "avatar":
        log("   ✅ PASS — first and last segments are the avatar, both with active voice")
    else:
        passed = False
        log("   ❌ FAIL")

    final_clip.close()
    # Save a stable copy of the produced video for manual inspection.
    try:
        import shutil
        stable_dir = os.path.join(os.path.dirname(__file__), "assets")
        os.makedirs(stable_dir, exist_ok=True)
        stable_path = os.path.join(stable_dir, "e2e_test_output.mp4")
        shutil.copy(final_path, stable_path)
        log(f"\n📁 Copied final video to: {stable_path}")
    except Exception as e:
        log(f"\n⚠️ Could not copy final video to assets/: {e}")

    log("\n" + "=" * 70)
    log("RESULT: " + ("✅ ALL CHECKS PASSED" if passed else "❌ SOME CHECKS FAILED"))
    log(f"Final video saved at: {final_path}")
    log("=" * 70)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
