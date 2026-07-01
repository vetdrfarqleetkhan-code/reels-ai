from __future__ import annotations

import json
import sys
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

import streamlit as st
from PIL import Image

from reels_ai.alignment import CaptionEvent, align_script_to_words, save_alignment, script_tokens, transcribe_audio
from reels_ai.audio import VOICE_PRESETS, generate_voiceover, save_uploaded_audio
from reels_ai.captions import resolve_font
from reels_ai.generator import render_reel_fast, select_audio_source
from reels_ai.planning import anchored_scene_timings, equal_scene_timings, timings_as_rows
from reels_ai.preview import static_preview
from reels_ai.storage import list_projects, load_project, save_project
from reels_ai.utils import OUTPUT_DIR, PROJECTS_DIR, TEMP_DIR, configure_logging, ensure_directories, media_duration, safe_name, sha256_bytes

ensure_directories(); log = configure_logging()
st.set_page_config(page_title="Reels AI", page_icon="🎬", layout="wide")

DEFAULTS = {
    "script": "", "scene_count": 3, "scene_files": {}, "alignment": [], "audio_path": "", "generated_audio_path": "",
    "rendered_path": "", "project_name": "Untitled Reel", "caption_fill": "#FFD400", "caption_outline": "#000000",
}
for key, value in DEFAULTS.items():
    if key not in st.session_state: st.session_state[key] = value.copy() if isinstance(value, (dict, list)) else value

st.markdown("""<style>
.block-container{padding-top:1.5rem;max-width:1500px}.preview-box img,.preview-box video{aspect-ratio:9/16;object-fit:cover;border-radius:22px;background:#111;max-height:720px;margin:auto;display:block}
[data-testid="stVideo"] video{aspect-ratio:9/16;object-fit:contain;background:#111;max-height:720px}
.small-note{color:#8991a3;font-size:.85rem}
</style>""", unsafe_allow_html=True)
st.title("Reels AI")
st.caption("Build a vertical reel from a script, ordered scene images, optional music, voiceover, and synchronized captions.")

def add_scene(): st.session_state.scene_count += 1
def remove_scene():
    if st.session_state.scene_count > 1:
        st.session_state.scene_files.pop(st.session_state.scene_count, None); st.session_state.scene_count -= 1
def clear_voice(): st.session_state.audio_path = ""

left, right = st.columns([1.55, .75], gap="large")
with left:
    with st.expander("Project", expanded=False):
        st.text_input("Project name", key="project_name")
        c1, c2, c3 = st.columns(3)
        if c1.button("New Reel", use_container_width=True):
            for k in list(DEFAULTS): st.session_state[k] = DEFAULTS[k].copy() if isinstance(DEFAULTS[k], (dict,list)) else DEFAULTS[k]
            st.rerun()
        if c2.button("Save Draft", use_container_width=True):
            files = {f"scene-{i}-{f.name}": f.getvalue() for i,f in st.session_state.scene_files.items() if f}
            config = {"voice_source": st.session_state.get("voice_source", "Generate voiceover"), "caption_fill": st.session_state.caption_fill}
            folder = save_project(st.session_state.project_name, config, st.session_state.get("script", ""), files); st.success(f"Saved to {folder.name}")
        projects = list_projects()
        chosen = c3.selectbox("Open Draft", [""] + [p["title"] for p in projects], label_visibility="collapsed")
        if chosen:
            project = next(p for p in projects if p["title"] == chosen)
            if st.button("Open selected project"):
                config, script = load_project(Path(project["path"])); st.session_state.script = script; st.session_state.project_name = config.get("title", chosen); st.rerun()

    st.subheader("1 · Script")
    pasted = st.text_area("Paste your script", height=190, key="script", placeholder="Paste the complete narration here…")
    txt = st.file_uploader("Or upload a .txt file", type=["txt"])
    use_file = st.checkbox("Use uploaded text instead of pasted text", disabled=txt is None)
    original_script_text = (txt.getvalue().decode("utf-8-sig") if txt and use_file else pasted).strip()

    st.subheader("2 · Ordered scenes")
    for i in range(1, st.session_state.scene_count + 1):
        uploaded = st.file_uploader(f"Scene {i}", type=["jpg","jpeg","png","webp"], key=f"scene_uploader_{i}")
        if uploaded: st.session_state.scene_files[i] = uploaded
    a,b = st.columns(2); a.button("＋ Add more image", on_click=add_scene, use_container_width=True); b.button("－ Remove image", on_click=remove_scene, use_container_width=True)
    ordered = [st.session_state.scene_files[i] for i in sorted(st.session_state.scene_files) if st.session_state.scene_files[i]]
    if ordered:
        st.caption("Image order")
        for i, file in enumerate(ordered, 1):
            c1,c2,c3,c4 = st.columns([1,4,1,1]); c1.image(file.getvalue(), width=55); c2.write(f"Scene {i} · {file.name}")
            if c3.button("↑", key=f"up_{i}", disabled=i==1):
                keys=sorted(st.session_state.scene_files); st.session_state.scene_files[keys[i-2]],st.session_state.scene_files[keys[i-1]]=st.session_state.scene_files[keys[i-1]],st.session_state.scene_files[keys[i-2]]; st.rerun()
            if c4.button("↓", key=f"down_{i}", disabled=i==len(ordered)):
                keys=sorted(st.session_state.scene_files); st.session_state.scene_files[keys[i-1]],st.session_state.scene_files[keys[i]]=st.session_state.scene_files[keys[i]],st.session_state.scene_files[keys[i-1]]; st.rerun()

    st.subheader("3 · Thumbnail")
    thumbnail = st.file_uploader("Optional thumbnail", type=["jpg","jpeg","png","webp"])
    use_thumbnail = st.checkbox("Use thumbnail as intro screen in the reel")
    thumb_duration = st.slider("Thumbnail intro duration", .2, 2.0, .5, .1, disabled=not use_thumbnail)

    st.subheader("4 · Voiceover")
    voice_source = st.radio("Voice source", ["Generate voiceover", "Upload voiceover"], horizontal=True, key="voice_source")
    uploaded_audio = None
    if voice_source == "Generate voiceover":
        preset = st.selectbox("Voice preset", list(VOICE_PRESETS), index=0)
        c1,c2,c3 = st.columns(3); gender=c1.selectbox("Gender", ["Male","Female"]); tone=c2.selectbox("Tone", ["Soft","Deep","Storytelling","Narration","Mystery","Documentary","Calm Islamic narration"]); speed=c3.selectbox("Speaking speed", ["Slow","Slightly slow","Normal","Fast"], index=1)
        honorifics = st.selectbox("Honorific handling", ["Keep visually only","Speak full honorific","Remove from generated speech"])
        if st.button("Preview / Generate Voice", disabled=not original_script_text):
            try:
                path = TEMP_DIR / "generated-voiceover.mp3"; generate_voiceover(original_script_text[:500] if st.session_state.get("preview_only") else original_script_text, path, preset, speed, honorifics); st.session_state.generated_audio_path=str(path); st.audio(str(path))
            except Exception as exc: log.exception("TTS failed"); st.error(f"Voice generation failed: {exc}")
    else:
        uploaded_audio = st.file_uploader("Upload voiceover", type=["mp3","wav","m4a","aac","ogg","flac"])
        if uploaded_audio:
            path=save_uploaded_audio(uploaded_audio.getvalue(), uploaded_audio.name, TEMP_DIR); st.session_state.audio_path=str(path); st.write(uploaded_audio.name); st.audio(uploaded_audio.getvalue())
        st.button("Clear uploaded voiceover", on_click=clear_voice)

    selected_audio_value = st.session_state.audio_path if voice_source == "Upload voiceover" else st.session_state.generated_audio_path
    audio_path = Path(selected_audio_value) if selected_audio_value else None
    audio_ready = bool(audio_path and audio_path.is_file())
    if audio_ready and not original_script_text:
        st.info("Voiceover ready. Add or upload the script in section 1, then generate timestamps.")
    elif not audio_ready:
        st.caption("Upload or generate a voiceover to activate timestamp generation.")
    if st.button("Generate timestamps", type="primary", disabled=not audio_ready):
        try:
            if not original_script_text:
                raise ValueError("Add or upload a script before generating timestamps.")
            with st.status("Preparing transcription…") as status:
                def transcription_progress(message: str) -> None:
                    status.update(label=message)
                words=transcribe_audio(audio_path, model_size="base.en", progress=transcription_progress)
                status.update(label="Aligning original script tokens…")
                events=align_script_to_words(original_script_text, words); st.session_state.alignment=[e.__dict__ for e in events]
                save_alignment(events, OUTPUT_DIR/"word_alignment.json", sha256_bytes(original_script_text.encode()), sha256_bytes(audio_path.read_bytes())); status.update(label="Timestamps ready", state="complete")
        except Exception as exc: log.exception("Timestamp generation failed"); st.error(f"Timestamp generation failed: {exc}")
    events=[CaptionEvent(**e) for e in st.session_state.alignment]
    if events:
        with st.expander("Alignment debugging and manual correction"):
            rows=[{"caption token":e.token,"matched spoken word(s)":e.matched,"start time":e.start,"end time":e.end,"confidence":round(e.confidence,2),"fallback used":e.fallback} for e in events]
            edited=st.data_editor(rows, disabled=["caption token","matched spoken word(s)","confidence","fallback used"], use_container_width=True)
            if st.button("Save timing corrections"):
                for event,row in zip(events,edited): event.start=float(row["start time"]); event.end=float(row["end time"])
                st.session_state.alignment=[e.__dict__ for e in events]; save_alignment(events, OUTPUT_DIR/"word_alignment.json"); st.success("Corrections saved.")

    st.subheader("5 · Image timing")
    timing_mode=st.selectbox("Image timing mode", ["Word-anchored timing","Automatic timing","Equal timing","Manual timing"])
    anchor_indices=[]
    if events and timing_mode=="Word-anchored timing":
        token_options=[f"{i+1}: {e.token}" for i,e in enumerate(events)]
        for i in range(len(ordered)):
            default=min(len(events)-1, round(i*len(events)/max(1,len(ordered))))
            anchor_indices.append(token_options.index(st.selectbox(f"Scene {i+1} begins at",token_options,index=default,key=f"anchor_{i}")))

    st.subheader("6 · Captions & motion")
    style=st.selectbox("Caption style", ["Pop Yellow Shorts","Clean Bold","Minimal"])
    c1,c2,c3=st.columns(3); position=c1.selectbox("Caption position",["Center","Lower middle","Bottom safe"],index=1); font=c2.selectbox("Caption font",["Arial Black","Poppins","Montserrat","Impact","Anton","Bebas Neue","Arial"]); size=c3.slider("Caption size",60,180,112)
    c1,c2,c3=st.columns(3); fill=c1.color_picker("Caption fill",key="caption_fill"); outline_color=c2.color_picker("Outline",key="caption_outline"); outline=c3.slider("Outline thickness",0,18,8)
    c1,c2,c3=st.columns(3); shadow=c1.checkbox("Shadow",True); animation=c2.selectbox("Animation",["Pop / overshoot","Scale in","Fade","None"]); sync=c3.selectbox("Caption sync mode",["Exact audio timestamps","Slightly early","Slightly late"])
    fine_ms=st.number_input("Manual global fine adjustment (ms)",-1000,1000,0,10)
    c1,c2,c3=st.columns(3); motion=c1.selectbox("Image motion intensity",["None","Low","Medium","High"],index=2); transition=c2.selectbox("Transition",["Cut","Crossfade","Fade","Slide","Cinematic reveal"],index=1); render_speed=c3.selectbox("Render speed",["Fast","Balanced","Maximum quality"],index=0)
    caption_settings={"font":font,"size":size,"fill":fill,"outline_color":outline_color,"outline":outline,"position":position,"shadow":shadow,"uppercase":style=="Pop Yellow Shorts"}
    _, font_warning=resolve_font(font)
    if font_warning: st.warning(font_warning)

    st.subheader("7 · Background music")
    music_upload=st.file_uploader("Upload background music",type=["mp3","wav","m4a","aac","ogg","flac"])
    auto_music=st.checkbox("Auto-select relevant music")
    category=st.selectbox("Music category",["Calm / Islamic","Mystery","Cinematic","Facts","Emotional","Ambient"],disabled=not auto_music)
    music_volume=st.slider("Music volume",0.0,.5,.10,.01); st.caption(f"Add local tracks under: {ROOT / 'assets' / 'music'}")

with right:
    platform=st.selectbox("Device / platform",["Instagram Reel","YouTube Shorts","TikTok"]); guides=st.checkbox("Show safe-area overlays")
    selected_scene = st.slider("Inspect scene", 1, len(ordered), 1) if len(ordered) > 1 else 1
    if len(ordered) <= 1: st.caption("Inspect scene · 1")
    preview_caption=(events[0].token if events else (script_tokens(original_script_text)[0] if original_script_text else "YOUR CAPTION"))
    st.markdown('<div class="preview-box">',unsafe_allow_html=True)
    if st.session_state.rendered_path and Path(st.session_state.rendered_path).exists(): st.video(st.session_state.rendered_path)
    else:
        image_data=ordered[selected_scene-1].getvalue() if ordered else None; st.image(static_preview(image_data,preview_caption,caption_settings,platform,guides),use_container_width=True)
    st.markdown('</div>',unsafe_allow_html=True)
    output_name=st.text_input("Output filename","reel.mp4")
    if st.button("Generate Reel",type="primary",use_container_width=True):
        try:
            if not original_script_text: raise ValueError("Add a script.")
            if not ordered: raise ValueError("Upload at least one scene image.")
            selected_audio=select_audio_source(voice_source,Path(st.session_state.audio_path) if st.session_state.audio_path else None,Path(st.session_state.generated_audio_path) if st.session_state.generated_audio_path else None)
            if not events: raise ValueError("Generate timestamps before rendering.")
            duration=media_duration(selected_audio)
            timings=anchored_scene_timings([f.name for f in ordered],anchor_indices,events,duration) if timing_mode=="Word-anchored timing" else equal_scene_timings([f.name for f in ordered],duration)
            scene_paths=[]
            for i,file in enumerate(ordered): p=TEMP_DIR/f"scene-{i}-{safe_name(file.name)}"; p.write_bytes(file.getvalue()); scene_paths.append(p)
            thumb_path=None
            if thumbnail and use_thumbnail: thumb_path=TEMP_DIR/f"thumbnail-{safe_name(thumbnail.name)}"; thumb_path.write_bytes(thumbnail.getvalue())
            music_path=None
            if music_upload: music_path=TEMP_DIR/f"music-{safe_name(music_upload.name)}"; music_path.write_bytes(music_upload.getvalue())
            elif auto_music:
                folder={"Calm / Islamic":"calm-islamic"}.get(category,category.lower())
                tracks=[p for p in (ROOT/"assets"/"music"/folder).glob("*") if p.suffix.lower() in {".mp3",".wav",".m4a",".ogg",".flac"}]
                if tracks: music_path=tracks[0]
                else: st.info("No local track exists in that category; continuing without music.")
            if not output_name.lower().endswith(".mp4"): output_name += ".mp4"
            out=OUTPUT_DIR/safe_name(output_name,"reel.mp4"); bar=st.progress(0,text="Preparing files")
            render_reel_fast(scene_paths,timings,selected_audio,events,out,caption_settings,motion,transition,thumb_path,thumb_duration,music_path,music_volume,fine_ms/1000,progress=lambda msg,val:bar.progress(val,text=msg),render_speed=render_speed)
            st.session_state.rendered_path=str(out); st.rerun()
        except Exception as exc: log.exception("Rendering failed"); st.error(f"Could not render: {exc}")
    if st.session_state.rendered_path and Path(st.session_state.rendered_path).exists():
        out=Path(st.session_state.rendered_path); st.download_button("Download MP4",out.read_bytes(),file_name=out.name,mime="video/mp4",use_container_width=True); st.caption(f"1080×1920 · {out.stat().st_size/1024/1024:.1f} MB")

with st.expander("Saved Reels"):
    for project in list_projects(): st.write(f"**{project.get('title','Untitled')}** · {project.get('saved_at','')[:10]}")
