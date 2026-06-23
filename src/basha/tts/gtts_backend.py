import io
import time
from gtts import gTTS
from basha.tts.base import TTSBackend

class GTTSBackend(TTSBackend):
    """
    gTTS - Google Text-to-Speech (offline - Uses Google Translate API)
    """
    def synthesize(self, text: str, lang: str, voice: str = None) -> bytes:
        """
        Turns text into speech using gTTS and returns the MP3 audio bytes.
        Includes a retry-with-backoff mechanism to handle Google Translate rate limits.
        """
        for attempt in range(3):
            try:
                tts = gTTS(text=text, lang=lang, slow=False)
                fp = io.BytesIO()
                tts.write_to_fp(fp)
                fp.seek(0)
                return fp.read()
            except Exception as e:
                if attempt == 2:
                    raise e
                # Wait 2s, then 4s, etc., before retrying
                time.sleep(2.0 * (attempt + 1))
        return b''
    