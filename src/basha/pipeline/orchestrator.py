import io
import time
from typing import List, Dict, Optional, Tuple, Any
from pydub import AudioSegment
from basha.pipeline.chunker import split_text_into_chunks
from basha.script.parser import parse_dialogue
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

    def process(self, text: str, target_lang: str, backend: str = "auto", voice: str = None, gender: str = None) -> Tuple[bytes, Dict[str, Any]]:
        """
        Runs the full text -> chunk -> translate -> tts -> stitch pipeline.
        Returns a tuple of (audio_bytes, metrics).
        """
        empty_metrics = {
            "translation_time": 0.0,
            "synthesis_time": 0.0,
            "cache_hits": 0,
            "total_chunks": 0,
            "cache_savings": 0.0,
            "duration": 0.0,
            "rtf": 0.0,
        }
        if not text.strip():
            return b'', empty_metrics

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

        translation_time = 0.0
        synthesis_time = 0.0
        cache_hits = 0

        with LogContext("basha.pipeline", "orchestrator_process", {"target_lang": target_lang, "backend": backend_name, "voice": voice}):
            # 1. Chunk the long text
            chunks = split_text_into_chunks(text)
            self.logger.info(f"Split input text into {len(chunks)} chunk(s)")
            total_chunks = len(chunks)

            audio_clips = []

            # 2. Process each chunk
            for idx, chunk in enumerate(chunks):
                # Translate this chunk
                t_start = time.perf_counter()
                with LogContext("basha.pipeline", f"translate_chunk_{idx}", {"chunk_len": len(chunk)}):
                    translated = self.translator.translate(chunk, target_lang)
                translation_time += time.perf_counter() - t_start

                # Check if this translated chunk already has audio saved (including voice)
                cached_audio = self.cache.get(translated, target_lang, voice=voice, backend=backend_name)
                if cached_audio is not None:
                    self.logger.info(f"Cache hit for chunk {idx}")
                    audio_clips.append(cached_audio)
                    cache_hits += 1
                else:
                    self.logger.info(f"Cache miss for chunk {idx}. Synthesizing with {backend_name}...")
                    s_start = time.perf_counter()
                    with LogContext("basha.pipeline", f"synthesize_chunk_{idx}", {"translated_len": len(translated)}):
                        clip = tts_backend.synthesize(translated, lang=target_lang, voice=voice)
                    synthesis_time += time.perf_counter() - s_start
                    
                    # Cache the newly generated audio (including voice)
                    self.cache.set(translated, target_lang, clip, voice=voice, backend=backend_name)
                    audio_clips.append(clip)

            # 3. Stitch audio clips together
            with LogContext("basha.pipeline", "stitch_audio_clips", {"num_clips": len(audio_clips)}):
                final_audio = stitch_audio_chunks(audio_clips)

            cache_savings = (cache_hits / total_chunks * 100.0) if total_chunks > 0 else 0.0

            duration_seconds = 0.0
            if final_audio:
                try:
                    segment = AudioSegment.from_file(io.BytesIO(final_audio))
                    duration_seconds = len(segment) / 1000.0
                except Exception:
                    pass

            total_processing_time = translation_time + synthesis_time
            rtf = total_processing_time / duration_seconds if duration_seconds > 0 else 0.0

            metrics = {
                "translation_time": translation_time,
                "synthesis_time": synthesis_time,
                "cache_hits": cache_hits,
                "total_chunks": total_chunks,
                "cache_savings": cache_savings,
                "duration": duration_seconds,
                "rtf": rtf,
            }

            return final_audio, metrics

    # ------------------------------------------------------------------
    # Multi-voice audio-drama rendering
    # ------------------------------------------------------------------
    def process_scene(
        self,
        script: str,
        target_lang: str = "en",
        translate: bool = True,
        voice_map: Optional[Dict[str, str]] = None,
    ) -> Tuple[bytes, Dict[str, str], List[Dict[str, str]], Dict[str, float]]:
        """Render a multi-character script into a single multi-voice audio scene.

        Steps: parse speakers -> assign a distinct voice per character (explicit
        map first, then auto round-robin) -> (optional) translate each line ->
        synthesize with Edge-TTS -> stitch into one track.

        Returns the audio bytes, resolved cast, transcript, and performance metrics.
        """
        import time
        import io
        from pydub import AudioSegment

        if not script.strip():
            return b'', {}, [], {"synthesis_time": 0.0, "duration": 0.0, "rtf": 0.0}

        start_time = time.perf_counter()
        lines = parse_dialogue(script)

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

        synthesis_time = time.perf_counter() - start_time
        duration_seconds = 0.0
        if final_audio:
            try:
                segment = AudioSegment.from_file(io.BytesIO(final_audio))
                duration_seconds = len(segment) / 1000.0
            except Exception:
                pass

        rtf = synthesis_time / duration_seconds if duration_seconds > 0 else 0.0
        metrics = {
            "synthesis_time": synthesis_time,
            "duration": duration_seconds,
            "rtf": rtf,
        }

        self.logger.info(f"Scene rendered: {len(lines)} lines, cast={cast}, metrics={metrics}")
        return final_audio, cast, transcript, metrics