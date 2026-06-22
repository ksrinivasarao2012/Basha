from typing import Dict, Type
from basha.tts.base import TTSBackend
from basha.tts.gtts_backend import GTTSBackend
from basha.tts.sarvam import SarvamBackend
from basha.tts.edge_tts import EdgeTTSBackend
from basha.core.config import settings

class TTSFactory:
    """
    Dynamic resolver for text-to-speech backend engines.
    """
    _backends: Dict[str, Type[TTSBackend]] = {
        "gtts": GTTSBackend,
        "sarvam": SarvamBackend,
        "edge": EdgeTTSBackend
    }

    @classmethod
    def get_backend(cls, name: str, lang: str = None) -> TTSBackend:
        """
        Resolves and returns the requested TTSBackend instance.
        
        :param name: The name of the backend ('gtts', 'sarvam', or 'auto').
        :param lang: The language code (used for 'auto' resolution).
        :return: An instance of a TTSBackend.
        """
        name = (name or "auto").lower()

        if name == "auto":
            # Determine best backend based on language and credentials.
            # Sarvam supports these Indian languages (and Indian English).
            sarvam_languages = {"hi", "te", "ta", "kn", "ml", "mr", "en", "bn", "gu", "pa", "or"}
            
            has_key = bool(settings.sarvam_api_key)
            is_supported_lang = lang and lang.lower() in sarvam_languages
            
            if has_key and is_supported_lang:
                return SarvamBackend()
            else:
                return GTTSBackend()
        
        if name in cls._backends:
            return cls._backends[name]()
            
        # Fallback to gTTS if unknown
        return GTTSBackend()
