from __future__ import annotations

import tempfile
import subprocess
from pathlib import Path
from typing import Callable

import numpy as np
from PIL import Image

from .alignment import CaptionEvent
from .captions import draw_caption, event_at
from .planning import SceneTiming, validate_scene_timings
from .utils import FPS, VIDEO_HEIGHT, VIDEO_WIDTH, configure_moviepy, cover_crop, ffmpeg_executable

RENDER_CONFIG = {"codec": "libx264", "audio_codec": "aac", "fps": FPS, "ffmpeg_params": ["-pix_fmt", "yuv420p"], "logger": None}


def _ass_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    hours = int(seconds // 3600)
    minutes = int(seconds % 3600 // 60)
    secs = seconds % 60
    return f"{hours}:{minutes:02d}:{secs:05.2f}"


def _ass_color(value: str) -> str:
    value = value.lstrip("#")
    if len(value) != 6:
        value = "FFFFFF"
    return f"&H00{value[4:6]}{value[2:4]}{value[0:2]}"


def _write_ass(path: Path, events: list[CaptionEvent], settings: dict, intro: float, offset: float) -> None:
    position = settings.get("position", "Lower middle")
    alignment = 5 if position == "Center" else 2
    margin_v = 0 if position == "Center" else (410 if position == "Lower middle" else 230)
    font = settings.get("font", "Arial Black")
    size = int(settings.get("size", 112))
    primary = _ass_color(settings.get("fill", "#FFD400"))
    outline = _ass_color(settings.get("outline_color", "#000000"))
    outline_width = int(settings.get("outline", 8))
    shadow = 3 if settings.get("shadow", True) else 0
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {VIDEO_WIDTH}
PlayResY: {VIDEO_HEIGHT}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,{font},{size},{primary},{primary},{outline},&H80000000,-1,0,0,0,100,100,0,0,1,{outline_width},{shadow},{alignment},60,60,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    for event in events:
        start = max(0.0, event.start + intro + offset)
        end = max(start + .01, event.end + intro + offset)
        token = event.token.upper() if settings.get("uppercase", True) else event.token
        token = token.replace("\\", r"\backslash").replace("{", r"\{").replace("}", r"\}")
        animation = r"{\fscx82\fscy82\t(0,90,\fscx110\fscy110)\t(90,170,\fscx100\fscy100)}"
        lines.append(f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Caption,,0,0,0,,{animation}{token}\n")
    path.write_text("".join(lines), encoding="utf-8-sig")


def render_reel_fast(
    scene_paths: list[Path], timings: list[SceneTiming], voiceover: Path, events: list[CaptionEvent],
    output: Path, caption_settings: dict, motion: str = "Medium", transition: str = "Crossfade",
    thumbnail: Path | None = None, thumbnail_duration: float = .5, music: Path | None = None,
    music_volume: float = .10, caption_offset: float = 0.0, progress: Callable[[str, float], None] | None = None,
    render_speed: str = "Fast",
) -> Path:
    """Render entirely in FFmpeg, avoiding the expensive Python-per-frame loop."""
    progress = progress or (lambda _message, _value: None)
    scene_paths = [Path(path).resolve() for path in scene_paths]
    voiceover = Path(voiceover).resolve()
    output = Path(output).resolve()
    thumbnail = Path(thumbnail).resolve() if thumbnail else None
    music = Path(music).resolve() if music else None
    if len(scene_paths) != len(timings):
        raise ValueError("Every uploaded image must have one scene timing.")
    configure_moviepy()
    from moviepy.editor import AudioFileClip

    probe = AudioFileClip(str(voiceover))
    try:
        voice_duration = probe.duration
    finally:
        probe.close()
    validate_scene_timings(timings, voice_duration)
    intro = thumbnail_duration if thumbnail else 0.0
    total_duration = voice_duration + intro
    # Only the slow photographic motion uses a reduced source rate; captions
    # and the exported video remain at the required stable 30 fps.
    profiles = {
        "Fast": (10, "superfast", "22", 720, 1280),
        "Balanced": (15, "superfast", "21", 900, 1600),
        "Maximum quality": (30, "veryfast", "20", VIDEO_WIDTH, VIDEO_HEIGHT),
    }
    motion_fps, encoder_preset, crf, motion_width, motion_height = profiles.get(render_speed, profiles["Fast"])
    output.parent.mkdir(parents=True, exist_ok=True)
    progress("Preparing images", .05)

    with tempfile.TemporaryDirectory(prefix="reels_ai_fast_") as temp_name:
        temp = Path(temp_name)
        image_specs: list[tuple[Path, float]] = []
        if thumbnail:
            frame = temp / "frame-000.jpg"
            cover_crop(Image.open(thumbnail)).save(frame, "JPEG", quality=94, subsampling=0)
            image_specs.append((frame, thumbnail_duration))
        for index, (source, timing) in enumerate(zip(scene_paths, timings), start=len(image_specs)):
            frame = temp / f"frame-{index:03d}.jpg"
            cover_crop(Image.open(source)).save(frame, "JPEG", quality=94, subsampling=0)
            image_specs.append((frame, timing.duration))

        ass_path = temp / "captions.ass"
        _write_ass(ass_path, events, caption_settings, intro, caption_offset)
        command = [ffmpeg_executable(), "-y", "-hide_banner", "-loglevel", "error"]
        for frame, duration in image_specs:
            command += ["-loop", "1", "-framerate", str(motion_fps), "-t", f"{duration:.6f}", "-i", str(frame)]
        voice_index = len(image_specs)
        command += ["-i", str(voiceover)]
        music_index = None
        if music:
            music_index = voice_index + 1
            command += ["-stream_loop", "-1", "-i", str(music)]

        filters: list[str] = []
        strength = {"None": 0.0, "Low": .025, "Medium": .05, "High": .08}.get(motion, .05)
        labels = []
        for index, (_frame, duration) in enumerate(image_specs):
            frames = max(2, round(duration * motion_fps))
            if strength:
                if index % 2:
                    zoom = f"1+{strength:.5f}*(1-on/{frames - 1})"
                else:
                    zoom = f"1+{strength:.5f}*on/{frames - 1}"
                video_filter = f"zoompan=z='{zoom}':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s={motion_width}x{motion_height}:fps={motion_fps},fps={FPS}"
            else:
                video_filter = f"scale={motion_width}:{motion_height}:flags=bicubic,fps={FPS}"
            if transition != "Cut" and duration > .4:
                fade = min(.18, duration / 4)
                video_filter += f",fade=t=in:st=0:d={fade:.3f},fade=t=out:st={duration-fade:.3f}:d={fade:.3f}"
            filters.append(f"[{index}:v]{video_filter},trim=duration={duration:.6f},setpts=PTS-STARTPTS[v{index}]")
            labels.append(f"[v{index}]")
        filters.append(f"{''.join(labels)}concat=n={len(labels)}:v=1:a=0[base]")
        filters.append(f"[base]scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:flags=bicubic,ass=filename='captions.ass'[vout]")

        delay_ms = round(intro * 1000)
        filters.append(f"[{voice_index}:a]adelay={delay_ms}|{delay_ms},apad,atrim=duration={total_duration:.6f}[voice]")
        if music_index is not None:
            fade = min(1.0, total_duration / 4)
            filters.append(f"[{music_index}:a]volume={music_volume:.4f},atrim=duration={total_duration:.6f},afade=t=in:st=0:d={fade:.3f},afade=t=out:st={total_duration-fade:.3f}:d={fade:.3f}[music]")
            filters.append("[voice][music]amix=inputs=2:duration=longest:dropout_transition=0[aout]")
        else:
            filters.append("[voice]anull[aout]")

        command += [
            "-filter_complex", ";".join(filters), "-map", "[vout]", "-map", "[aout]",
            "-t", f"{total_duration:.6f}", "-r", str(FPS), "-c:v", "libx264", "-preset", encoder_preset,
            "-crf", crf, "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart", "-progress", "pipe:1", "-nostats", str(output),
        ]
        error_log = temp / "ffmpeg-error.log"
        progress("Encoding with FFmpeg", .12)
        with error_log.open("w", encoding="utf-8", errors="replace") as errors:
            process = subprocess.Popen(command, cwd=temp, stdout=subprocess.PIPE, stderr=errors, text=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            assert process.stdout is not None
            for line in process.stdout:
                if line.startswith("out_time_ms="):
                    try:
                        seconds = int(line.split("=", 1)[1]) / 1_000_000
                        fraction = min(.98, .12 + .86 * seconds / max(.01, total_duration))
                        progress(f"Encoding video - {min(seconds,total_duration):.0f}/{total_duration:.0f}s", fraction)
                    except ValueError:
                        pass
            return_code = process.wait()
        if return_code != 0:
            details = error_log.read_text(encoding="utf-8", errors="replace")[-2000:]
            raise RuntimeError(f"FFmpeg rendering failed: {details.strip()}")
        progress("Complete", 1.0)
        return output


def _motion_frame(base: Image.Image, t: float, duration: float, intensity: str, pattern: int) -> Image.Image:
    strength = {"None": 0.0, "Low": .025, "Medium": .055, "High": .09}.get(intensity, .055)
    progress = min(1.0, max(0.0, t / max(duration, .001)))
    if pattern % 2: progress = 1 - progress
    zoom = 1 + strength * progress
    w, h = round(VIDEO_WIDTH * zoom), round(VIDEO_HEIGHT * zoom)
    moved = base.resize((w, h), Image.Resampling.LANCZOS)
    pan_x = round((w - VIDEO_WIDTH) * ((pattern % 3) / 2 if w > VIDEO_WIDTH else 0))
    pan_y = (h - VIDEO_HEIGHT) // 2
    return moved.crop((pan_x, pan_y, pan_x + VIDEO_WIDTH, pan_y + VIDEO_HEIGHT))


def render_reel(
    scene_paths: list[Path], timings: list[SceneTiming], voiceover: Path, events: list[CaptionEvent],
    output: Path, caption_settings: dict, motion: str = "Medium", transition: str = "Crossfade",
    thumbnail: Path | None = None, thumbnail_duration: float = .5, music: Path | None = None,
    music_volume: float = .10, caption_offset: float = 0.0, progress: Callable[[str, float], None] | None = None,
) -> Path:
    configure_moviepy()
    from moviepy.audio.fx.all import audio_fadein, audio_fadeout, audio_loop
    from moviepy.editor import AudioFileClip, CompositeAudioClip, CompositeVideoClip, VideoClip, concatenate_videoclips

    progress = progress or (lambda _message, _value: None)
    output.parent.mkdir(parents=True, exist_ok=True)
    if len(scene_paths) != len(timings): raise ValueError("Every uploaded image must have one scene timing.")
    audio = music_clip = final_audio = final = None
    clips = []
    try:
        progress("Reading voiceover", .08)
        audio = AudioFileClip(str(voiceover))
        validate_scene_timings(timings, audio.duration)
        intro = thumbnail_duration if thumbnail else 0.0
        progress("Building scenes", .20)
        for index, (path, timing) in enumerate(zip(scene_paths, timings)):
            base = cover_crop(Image.open(path))
            duration = timing.duration
            def make_frame(t, b=base, d=duration, p=index, start=timing.start):
                frame = _motion_frame(b, t, d, motion, p)
                event = event_at(events, start + t, caption_offset)
                if event: frame = draw_caption(frame, event.token, caption_settings)
                return np.asarray(frame)
            clip = VideoClip(make_frame=make_frame, duration=duration)
            if transition in {"Crossfade", "Fade", "Cinematic reveal"} and index:
                clip = clip.crossfadein(min(.25, duration / 4))
            clips.append(clip)
        main = concatenate_videoclips(clips, method="compose")
        if thumbnail:
            thumb_base = cover_crop(Image.open(thumbnail))
            thumb = VideoClip(lambda _t, b=thumb_base: np.asarray(b), duration=thumbnail_duration)
            clips.append(thumb)
            video = concatenate_videoclips([thumb, main], method="compose")
        else:
            video = main
        progress("Mixing audio", .55)
        delayed_voice = audio.set_start(intro)
        tracks = [delayed_voice]
        if music:
            music_clip = AudioFileClip(str(music)).volumex(music_volume)
            target = video.duration
            if music_clip.duration < target: music_clip = audio_loop(music_clip, duration=target)
            else: music_clip = music_clip.subclip(0, target)
            music_clip = audio_fadeout(audio_fadein(music_clip, min(1.0, target/4)), min(1.0, target/4))
            tracks.insert(0, music_clip)
        final_audio = CompositeAudioClip(tracks).set_duration(video.duration)
        final = video.set_audio(final_audio).set_fps(FPS)
        progress("Exporting video", .70)
        with tempfile.TemporaryDirectory(prefix="reels_ai_") as tmp:
            temp_audio = str(Path(tmp) / "render-audio.m4a")
            final.write_videofile(str(output), temp_audiofile=temp_audio, remove_temp=True, **RENDER_CONFIG)
        progress("Complete", 1.0)
        return output
    finally:
        for resource in [final, final_audio, music_clip, audio, *clips]:
            try:
                if resource is not None: resource.close()
            except Exception: pass


def select_audio_source(source: str, uploaded: Path | None, generated: Path | None) -> Path:
    if source == "Upload voiceover":
        if not uploaded: raise ValueError("Upload a voiceover before rendering.")
        return uploaded
    if not generated: raise ValueError("Generate a voiceover before rendering.")
    return generated
