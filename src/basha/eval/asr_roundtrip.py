import io
import time
import speech_recognition as sr
from pydub import AudioSegment


class ASRRateLimited(RuntimeError):
    """Raised when the free Google recognizer rejects the request (usually a
    rate-limit / temporary block), as opposed to the audio being unintelligible."""

# Google STT needs full locale codes (e.g. "ta-IN"), not bare "ta". A missing
# mapping makes the transcriber return nothing -> a misleading 100% CER.
_ASR_LOCALE = {
    "en": "en-US", "hi": "hi-IN", "te": "te-IN", "ta": "ta-IN",
    "kn": "kn-IN", "ml": "ml-IN", "mr": "mr-IN", "bn": "bn-IN",
    "gu": "gu-IN", "pa": "pa-IN",
    "de": "de-DE", "fr": "fr-FR", "es": "es-ES", "it": "it-IT", "pt": "pt-PT",
}


def transcribe_audio_bytes(audio_bytes: bytes, lang: str = "en") -> str:
    """
    Transcribes audio bytes back into text using the speech_recognition Google API.
    Handles converting MP3 audio bytes into the required WAV format.
    """
    if not audio_bytes:
        return ""
        
    # 1. Convert MP3 bytes (or other audio formats) to WAV in memory
    audio_segment = AudioSegment.from_file(io.BytesIO(audio_bytes))
    wav_io = io.BytesIO()
    audio_segment.export(wav_io, format="wav")
    wav_io.seek(0)
    
    # 2. Load WAV into SpeechRecognition AudioFile
    recognizer = sr.Recognizer()
    with sr.AudioFile(wav_io) as source:
        audio_data = recognizer.record(source)
        
    # 3. Transcribe with Google Speech API, retrying transient rate-limits.
    lang_code = _ASR_LOCALE.get((lang or "en").lower(), lang)
    last_error = None
    for attempt in range(3):
        try:
            return recognizer.recognize_google(audio_data, language=lang_code)
        except sr.UnknownValueError:
            # Speech was genuinely unintelligible or silent — not a rate-limit.
            return ""
        except sr.RequestError as e:
            # Usually a rate-limit / temporary block on the free endpoint.
            last_error = e
            time.sleep(1.5 * (attempt + 1))   # back off and retry
    raise ASRRateLimited(f"Google ASR request rejected after retries: {last_error}")
