import io
from gtts import gTTS
from basha.tts.base import TTSBackend

class GTTSBackend(TTSBackend):
    """
    gTTS - Google Text-to-Speech (offline - Uses Google Translate API)
    """
    def synthesize(self,text:str,lang:str,voice:str =  None) -> bytes:
        """
        Turns text into speech using gTTS and returns the MP3 audio bytes.
        """
        # Create gTTS object
        tts = gTTS(text=text,lang = lang,slow =  False)

        # Save audio to a bytes buffer in memory
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)

        return fp.read()
    