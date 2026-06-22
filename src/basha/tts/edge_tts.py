import asyncio
from edge_tts import Communicate
from basha.tts.base import TTSBackend

# Edge-TTS needs a real VOICE ID (e.g. "en-US-AriaNeural"), not a bare language
# code. When the caller doesn't pass a voice we map the language to a sensible
# default voice so synthesis never fails. (The multi-voice scene path always
# passes an explicit voice ID, so this map is just the single-voice fallback.)
_DEFAULT_VOICE = {
    "en": "en-US-AriaNeural",
    "hi": "hi-IN-SwaraNeural",
    "te": "te-IN-ShrutiNeural",
    "ta": "ta-IN-PallaviNeural",
    "kn": "kn-IN-SapnaNeural",
    "ml": "ml-IN-SobhanaNeural",
    "mr": "mr-IN-AarohiNeural",
    "de": "de-DE-KatjaNeural",
    "fr": "fr-FR-DeniseNeural",
    "es": "es-ES-ElviraNeural",
    "it": "it-IT-ElsaNeural",
    "pt": "pt-BR-FranciscaNeural",
}


class EdgeTTSBackend(TTSBackend):
    """Microsoft Edge free neural TTS backend.

    Accepts an optional ``voice`` argument which must be a valid Edge-TTS voice ID
    (e.g. ``"en-US-JennyNeural"`` or ``"hi-IN-MadhavNeural"``). If ``voice`` is
    ``None`` a default voice for ``lang`` is used.
    """

    def synthesize(self, text: str, lang: str, voice: str = None) -> bytes:
        """Synthesize ``text`` and return raw MP3 bytes."""
        voice_id = voice or _DEFAULT_VOICE.get((lang or "en").lower(), "en-US-AriaNeural")

        async def _run():
            comm = Communicate(text, voice_id)
            # edge-tts has no in-memory "output"; we collect the audio chunks
            # off the stream ourselves and return them as bytes.
            buf = bytearray()
            async for chunk in comm.stream():
                if chunk["type"] == "audio":
                    buf.extend(chunk["data"])
            return bytes(buf)

        return asyncio.run(_run())
