from typing import List, Dict, Optional, Tuple
from basha.pipeline.chunker import split_text_into_chunks
from basha.pipeline.stitcher import stitch_audio_chunks
from basha.translation.deep_translator_backend import DeepTranslatorBackend
from basha.tts.factory import TTSFactory
from basha.tts.edge_tts import EdgeTTSBackend
from basha.tts.voices import VoiceManager
from basha.core.cache import AudioCache
from basha.core.logging import get_logger, LogContext
from basha.core.config import settings

class PipelineOrchestrator:
    """
    Orchestrates the entire translation + synthesis pipeline.
    """

    def __init__(self):
        # Instantiate our translation backend and cache
        self.translator = DeepTranslatorBackend()
        self.cache = AudioCache() 
        self.logger = get_logger("basha.pipeline")

    def process(self, text: str, target_lang: str, backend: str = "auto", voice: str = None, gender: str = None) -> bytes:
        """
        Runs the full text -> chunk -> translate -> tts -> stitch pipeline.
        """
        if not text.strip():
            return b''

        # A male/female choice only makes sense on Edge-TTS (gTTS has a single
        # voice per language). So when a gender is requested, resolve a matching
        # Edge voice and force the Edge backend.
        if gender and not voice:
            voice = VoiceManager().get_voice("__single__", target_lang, gender=gender)

        if voice:
            tts_backend = EdgeTTSBackend()
        else:
            # Resolve actual TTS backend dynamically using TTSFactory
            tts_backend = TTSFactory.get_backend(backend, target_lang)
        backend_name = tts_backend.__class__.__name__

        with LogContext("basha.pipeline", "orchestrator_process", {"target_lang": target_lang, "backend": backend_name, "voice": voice}):
            # 1. Chunk the long text
            chunks = split_text_into_chunks(text)
            self.logger.info(f"Split input text into {len(chunks)} chunk(s)")

            audio_clips = []

            # 2. Process each chunk
            for idx, chunk in enumerate(chunks):
                # Translate this chunk
                with LogContext("basha.pipeline", f"translate_chunk_{idx}", {"chunk_len": len(chunk)}):
                    translated = self.translator.translate(chunk, target_lang)

                # Check if this translated chunk already has audio saved (including voice)
                cached_audio = self.cache.get(translated, target_lang, voice=voice, backend=backend_name)
                if cached_audio is not None:
                    self.logger.info(f"Cache hit for chunk {idx}")
                    audio_clips.append(cached_audio)
                else:
                    self.logger.info(f"Cache miss for chunk {idx}. Synthesizing with {backend_name}...")
                    with LogContext("basha.pipeline", f"synthesize_chunk_{idx}", {"translated_len": len(translated)}):
                        clip = tts_backend.synthesize(translated, lang=target_lang, voice=voice)
                    
                    # Cache the newly generated audio (including voice)
                    self.cache.set(translated, target_lang, clip, voice=voice, backend=backend_name)
                    audio_clips.append(clip)

            # 3. Stitch audio clips together
            with LogContext("basha.pipeline", "stitch_audio_clips", {"num_clips": len(audio_clips)}):
                final_audio = stitch_audio_chunks(audio_clips)

            return final_audio

    # ------------------------------------------------------------------
    # Multi-voice audio-drama rendering
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_lines(script: str) -> List[Tuple[Optional[str], str]]:
        """Parse a script into (speaker, utterance) pairs.

        Each line is ``Speaker: text``. A line with no colon is treated as
        narration (speaker = None). Blank lines are skipped.
        """
        parsed: List[Tuple[Optional[str], str]] = []
        for line in script.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(":", 1)
            if len(parts) == 2 and parts[0].strip():
                parsed.append((parts[0].strip(), parts[1].strip()))
            else:
                parsed.append((None, line))
        return parsed

    def process_scene(
        self,
        script: str,
        target_lang: str = "en",
        translate: bool = True,
        voice_map: Optional[Dict[str, str]] = None,
    ) -> Tuple[bytes, Dict[str, str]]:
        """Render a multi-character script into a single multi-voice audio scene.

        Steps: parse speakers -> assign a distinct voice per character (explicit
        map first, then auto round-robin) -> (optional) translate each line ->
        synthesize with Edge-TTS -> stitch into one track.

        Returns the audio bytes and the resolved cast (speaker -> voice id).
        """
        if not script.strip():
            return b'', {}

        lines = self._parse_lines(script)

        # Validate any user-supplied map against the live voice list, then build
        # a manager that auto-assigns voices for unmapped characters.
        valid_map = VoiceManager.validate_explicit_map(voice_map, target_lang) if voice_map else {}
        vm = VoiceManager(valid_map)
        tts = EdgeTTSBackend()  # only Edge supports multiple distinct voices

        cast: Dict[str, str] = {}          # speaker -> voice id (stable per speaker)
        audio_clips: List[bytes] = []
        transcript: List[Dict[str, str]] = []   # speaker + (translated) line, for the UI

        with LogContext("basha.pipeline", "render_scene",
                        {"target_lang": target_lang, "lines": len(lines), "translate": translate}):
            for idx, (speaker, utterance) in enumerate(lines):
                speaker_key = speaker or "Narrator"
                # Assign a voice once per speaker so a character always sounds the same.
                if speaker_key not in cast:
                    cast[speaker_key] = vm.get_voice(speaker_key, target_lang)
                voice_id = cast[speaker_key]

                # Optionally localize the line.
                if translate and target_lang.lower() != "en":
                    utterance = self.translator.translate(utterance, target_lang)

                transcript.append({"speaker": speaker_key, "text": utterance})

                # Cache per (text, lang, voice) so re-renders are instant.
                cached = self.cache.get(utterance, target_lang, voice=voice_id, backend="EdgeTTSBackend")
                if cached is not None:
                    self.logger.info(f"Scene cache hit for line {idx} ({speaker_key})")
                    audio_clips.append(cached)
                else:
                    self.logger.info(f"Synthesizing line {idx}: {speaker_key} -> {voice_id}")
                    clip = tts.synthesize(utterance, lang=target_lang, voice=voice_id)
                    self.cache.set(utterance, target_lang, clip, voice=voice_id, backend="EdgeTTSBackend")
                    audio_clips.append(clip)

            final_audio = stitch_audio_chunks(audio_clips, pause_ms=300)

        self.logger.info(f"Scene rendered: {len(lines)} lines, cast={cast}")
        return final_audio, cast, transcript