import io
import shutil
from typing import List
from pydub import AudioSegment

# Locate ffmpeg/ffprobe WITHOUT hardcoding a machine-specific path. This works
# everywhere they're on PATH: Windows (winget/choco), macOS (brew), Linux/Docker
# (apt). A hardcoded path breaks the moment ffmpeg updates or the app is deployed.
_ffmpeg = shutil.which("ffmpeg")
_ffprobe = shutil.which("ffprobe")
if _ffmpeg:
    AudioSegment.converter = _ffmpeg
if _ffprobe:
    AudioSegment.ffprobe = _ffprobe



def stitch_audio_chunks(audio_clips: List[bytes], pause_ms: int = 150) -> bytes:
    """
    Stitches multiple audio segments (bytes) together into one continuous audio track
    using pydub. Adds a brief pause between segments for natural pacing.
    """
    if not audio_clips:
        return b''
    
    # Start with a null segment
    combined = AudioSegment.empty()

    # Create the silent segment to use as a pause
    silence = AudioSegment.silent(duration = pause_ms)
    for i, clip_bytes in enumerate(audio_clips):
        # Convert raw bytes into an AudioSegment
        # gTTS returns MP3 format audio bytes, but Sarvam returns WAV
        try:
            segment = AudioSegment.from_file(io.BytesIO(clip_bytes))
        except Exception:
            segment = AudioSegment.from_file(io.BytesIO(clip_bytes), format="wav")

        if i == 0:
            combined = segment
        else:
            # Append with a brief pause
            combined += silence + segment
    
    # Export combined audio to bytes in MP3 format
    out_fp = io.BytesIO()
    combined.export(out_fp, format = "mp3")
    out_fp.seek(0)
    return out_fp.read()