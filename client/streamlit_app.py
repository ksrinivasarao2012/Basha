import streamlit as st
import requests
import time

# Set page config for a premium look
st.set_page_config(
    page_title="Basha — Multilingual Narrator",
    page_icon="🎙️",
    layout="centered"
)

# API Server URLs
BASE_URL = "http://localhost:8000"
JOBS_URL = f"{BASE_URL}/jobs"
HEALTH_URL = f"{BASE_URL}/health"

# Title and Description
st.title("🎙️ Basha")
st.subheader("Multilingual Text-to-Speech & Localization")
st.write(
    "Paste English text below, choose a target language, "
    "and listen to the translated, natural voice narration."
)

# Sidebar - Health Status Check
st.sidebar.header("System Status")
try:
    health_response = requests.get(HEALTH_URL, timeout=2.0)
    if health_response.status_code == 200:
        status_data = health_response.json()
        if status_data.get("status") == "healthy":
            st.sidebar.success("🟢 API Server: Online & Healthy")
        else:
            st.sidebar.warning("🟡 API Server: Degraded (Check Internet)")
        
        # Display engine details
        st.sidebar.info(f"Engine: {status_data.get('active_engine', 'Unknown')}")
    else:
        st.sidebar.error("🔴 API Server: Off-line")
except Exception:
    st.sidebar.error("🔴 API Server: Off-line (Is uvicorn running?)")

# Sidebar - Cache controls
st.sidebar.markdown("---")
st.sidebar.subheader("Cache")
try:
    stats = requests.get(f"{BASE_URL}/cache/stats", timeout=2.0).json()
    st.sidebar.caption(f"{stats['cached_files']} files · {stats['total_mb']} MB")
except Exception:
    st.sidebar.caption("Cache stats unavailable")

if st.sidebar.button("🗑️ Clear Cache", use_container_width=True):
    try:
        r = requests.delete(f"{BASE_URL}/cache", timeout=5.0)
        if r.status_code == 200:
            st.sidebar.success("Cache cleared!")
        else:
            st.sidebar.error(f"Clear failed: {r.status_code}")
    except Exception as e:
        st.sidebar.error(f"Clear failed: {e}")

# Form inputs
text_to_synthesize = st.text_area(
    "English text to narrate:",
    value="Basha is an intelligent translation and text-to-speech platform designed to localise audio content.",
    height=150
)

# Language selection dictionary
languages = {
    "Telugu (తెలుగు)": "te",
    "Tamil (தமிழ்)": "ta",
    "Kannada (ಕನ್ನಡ)": "kn",
    "Malayalam (മലയാളം)": "ml",
    "Marathi (मराठी)": "mr",
    "Hindi (हिन्दी)": "hi",
    "German (Deutsch)": "de",
    "French (Français)": "fr",
    "Spanish (Español)": "es",
    "Italian (Italiano)": "it",
    "Portuguese (Português)": "pt"
}

selected_lang_name = st.selectbox("Translate and narrate to:", list(languages.keys()))
target_lang_code = languages[selected_lang_name]

# Voice gender. A male/female choice uses Edge-TTS neural voices.
gender_choice = st.radio(
    "Voice:",
    ["Female", "Male"],
    horizontal=True,
    help="Picks a male or female neural voice (Edge-TTS).",
)
gender_code = gender_choice.lower()

# Synthesize Button
if st.button("Generate Audio 🚀", use_container_width=True):
    if not text_to_synthesize.strip():
        st.error("Please enter some text first!")
    else:
        # Step 1: Submit background job
        status_text = st.empty()
        progress_bar = st.progress(0)
        
        status_text.info("Submitting text to synthesis queue...")
        
        try:
            payload = {
                "text": text_to_synthesize,
                "target_language": target_lang_code,
                "gender": gender_code
            }
            submit_resp = requests.post(JOBS_URL, json=payload)
            
            if submit_resp.status_code == 202:
                job_data = submit_resp.json()
                job_id = job_data["job_id"]
                
                # Step 2: Poll job status
                completed = False
                progress = 0
                
                while not completed:
                    time.sleep(0.5)
                    status_resp = requests.get(f"{JOBS_URL}/{job_id}")
                    if status_resp.status_code != 200:
                        status_text.error("Failed to check status.")
                        break
                        
                    job_status_data = status_resp.json()
                    status = job_status_data["status"]
                    
                    if status == "pending":
                        progress = min(progress + 5, 20)
                        progress_bar.progress(progress)
                        status_text.info("Job queued. Waiting for worker...")
                    elif status == "processing":
                        progress = min(progress + 8, 90)
                        progress_bar.progress(progress)
                        status_text.info("Translating, synthesizing, and stitching audio...")
                    elif status == "completed":
                        progress_bar.progress(100)
                        status_text.success("Audio generated successfully! 🎉")
                        completed = True
                        
                        # Step 3: Download resulting audio
                        audio_url = job_status_data["download_url"]
                        audio_resp = requests.get(audio_url)
                        if audio_resp.status_code == 200:
                            audio_bytes = audio_resp.content
                            st.audio(audio_bytes, format="audio/mp3")
                            
                            st.download_button(
                                label="Download MP3 📥",
                                data=audio_bytes,
                                file_name=f"basha_narration_{target_lang_code}.mp3",
                                mime="audio/mp3"
                            )
                            
                            # Step 4: Display Quality & Performance Metrics
                            metrics = job_status_data.get("metrics")
                            if metrics:
                                st.markdown("---")
                                st.markdown("### 📊 Performance")

                                rtf = metrics["rtf"]
                                col1, col2 = st.columns(2)
                                with col1:
                                    st.metric("Real-Time Factor (RTF)", f"{rtf:.3f}")
                                with col2:
                                    speedup = (1.0 / rtf) if rtf > 0 else 0
                                    st.metric("Speed vs real-time", f"{speedup:.1f}× faster")

                                st.caption(
                                    "RTF = synthesis time ÷ audio length. Below 1.0 means the "
                                    "audio is generated faster than it plays — good, even on CPU."
                                )

                                with st.expander("📝 Speech-recognition round-trip (sanity check)"):
                                    st.write(
                                        "We fed the generated audio back into a speech recognizer "
                                        "to confirm it produced real, recognizable speech:"
                                    )
                                    st.write(metrics["transcription"])
                        else:
                            st.error("Failed to download completed audio.")
                        break
                    elif status == "failed":
                        progress_bar.empty()
                        status_text.error(f"Synthesis job failed: {job_status_data.get('error')}")
                        break
            else:
                status_text.error(f"API Error ({submit_resp.status_code}): {submit_resp.text}")
                
        except Exception as e:
            status_text.error(f"Connection failed: {str(e)}")

# ===========================================================================
#  Multi-Voice Audio Drama (the differentiator)
# ===========================================================================
SCENE_URL = f"{BASE_URL}/scene"

st.markdown("---")
st.header("🎭 Multi-Voice Audio Drama")
st.write(
    "Write a script with one `Speaker: line` per row. Each character is "
    "automatically given a **distinct voice**, then the whole scene is "
    "translated, narrated, and stitched into a single audio clip."
)

scene_script = st.text_area(
    "Scene script (format: `Name: dialogue`):",
    value=(
        "Ravi: Meena, have you heard the news about the festival?\n"
        "Meena: Yes! I cannot wait. Are you coming with us?\n"
        "Ravi: Of course. Let us leave early in the morning.\n"
        "Narrator: And so their journey began."
    ),
    height=160,
    key="scene_script",
)

col_a, col_b = st.columns(2)
with col_a:
    scene_lang_name = st.selectbox(
        "Scene language:", list(languages.keys()), key="scene_lang"
    )
    scene_lang_code = languages[scene_lang_name]
with col_b:
    scene_translate = st.checkbox(
        "Translate the script into the scene language", value=True, key="scene_translate"
    )

if st.button("Render Scene 🎬", use_container_width=True, key="render_scene"):
    if not scene_script.strip():
        st.error("Please write a script first!")
    else:
        with st.spinner("Casting voices, translating, synthesizing, and stitching the scene..."):
            try:
                resp = requests.post(
                    SCENE_URL,
                    json={
                        "script": scene_script,
                        "target_language": scene_lang_code,
                        "translate": scene_translate,
                    },
                    timeout=120,
                )
                if resp.status_code == 200:
                    st.success("Scene rendered! 🎉")
                    st.audio(resp.content, format="audio/mp3")
                    st.download_button(
                        "Download Scene MP3 📥",
                        data=resp.content,
                        file_name=f"basha_scene_{scene_lang_code}.mp3",
                        mime="audio/mp3",
                        key="dl_scene",
                    )
                    # Show which voice each character was assigned (from the X-Cast header)
                    import json as _json
                    cast = _json.loads(resp.headers.get("X-Cast", "{}"))
                    if cast:
                        st.markdown("### 🎙️ Cast")
                        for character, voice in cast.items():
                            st.write(f"**{character}** → `{voice}`")
                else:
                    st.error(f"API Error ({resp.status_code}): {resp.text}")
            except Exception as e:
                st.error(f"Connection failed: {e}")

# Add a small footer
st.markdown("---")
