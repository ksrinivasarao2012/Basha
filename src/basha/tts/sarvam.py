import base64
import requests
from typing import Optional
from basha.tts.base import TTSBackend
from basha.core.config import settings

class SarvamBackend(TTSBackend):
    """
    Sarvam AI Text-to-Speech API Backend.
    Provides high-quality Indian regional language voices (Bulbul model).
    """
    def __init__(self):
        # Read parameters from config
        tts_config = settings.backends.get("tts", {})
        sarvam_config = tts_config.get("sarvam", {})
        self.endpoint = sarvam_config.get("endpoint", "https://api.sarvam.ai/text-to-speech")
        self.api_key = settings.sarvam_api_key

    def _map_language(self, lang: str) -> str:
        """
        Maps standard 2-letter language codes to Sarvam's expected locale format.
        """
        lang_mapping = {
            "hi": "hi-IN",
            "te": "te-IN",
            "ta": "ta-IN",
            "kn": "kn-IN",
            "ml": "ml-IN",
            "mr": "mr-IN",
            "en": "en-IN",
            "bn": "bn-IN",
            "gu": "gu-IN",
            "pa": "pa-IN",
            "or": "or-IN"
        }
        return lang_mapping.get(lang.lower(), "hi-IN")

    def synthesize(self, text: str, lang: str, voice: Optional[str] = None) -> bytes:
        """
        Sends text to Sarvam AI TTS API, decodes the base64 response,
        and returns the raw audio bytes (MP3 format).
        """
        if not self.api_key:
            raise ValueError("SARVAM_API_KEY is not set in environment or .env file.")

        headers = {
            "api-subscription-key": self.api_key,
            "Content-Type": "application/json"
        }

        # Select a default speaker if not provided.
        # Sarvam supports many voices; using a known valid default.
        speaker_voice = voice or "anushka"
        target_lang_code = self._map_language(lang)

        payload = {
            "inputs": [text],
            "target_language_code": target_lang_code,
            "speaker": speaker_voice,
            "pitch": 0,
            "pace": 1.0,
            "loudness": 1.5,
            "speech_sample_rate": 8000,
            "enable_preprocessing": True,
            "model": "bulbul:v2"
        }

        response = requests.post(self.endpoint, json=payload, headers=headers)

        if response.status_code != 200:
            raise RuntimeError(
                f"Sarvam API error ({response.status_code}): {response.text}"
            )

        data = response.json()
        audios = data.get("audios", [])
        if not audios:
            raise ValueError("No audio content returned from Sarvam API.")

        # Sarvam returns audio as a base64 encoded string
        base64_audio = audios[0]
        audio_bytes = base64.b64decode(base64_audio)
        return audio_bytes
