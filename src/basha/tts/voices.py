import asyncio
from typing import Dict, List, Optional

import edge_tts

# ---------------------------------------------------------------------------
# VoiceManager
# ---------------------------------------------------------------------------
# This module provides a robust way to obtain an Edge‑TTS voice ID for a given
# character (speaker) and target language.
#
# * Explicit mapping – a user‑supplied dict ``{'Ravi': 'hi-IN-MadhavNeural', ...}``
#   takes precedence.
# * Auto‑fallback – for speakers not present in the explicit map we select a
#   distinct voice from the pool of available voices for the language, using a
#   round‑robin strategy so that each new speaker gets a unique voice.
# * Live voice list – the list of voices is fetched at runtime from the Edge‑TTS
#   package (``edge-tts --list-voices``) to guarantee that the IDs are current.
#   The result is cached per language for the lifetime of the process.
# ---------------------------------------------------------------------------

class VoiceManager:
    """Manage voice selection for Edge‑TTS.

    Supports:
    * Explicit per‑speaker map.
    * Gender‑aware auto‑fallback (male/female). If a gender is supplied, the
      manager picks a voice from the pool that matches the requested gender.
    * General round‑robin fallback when gender is not specified.
    """
    """Manage voice selection for Edge‑TTS.

    Example usage::

        vm = VoiceManager(explicit_map={"Ravi": "hi-IN-MadhavNeural"})
        voice_id = vm.get_voice("Meena", target_lang="hi")
    """

    _voice_cache: Dict[str, List[str]] = {}
    _round_robin_index: Dict[str, int] = {}

    def __init__(self, explicit_map: Optional[Dict[str, str]] = None):
        #: Mapping of speaker name → voice ID that the user explicitly wants.
        self.explicit_map: Dict[str, str] = explicit_map or {}

    # ---------------------------------------------------------------------
    # Private helpers
    # ---------------------------------------------------------------------
    @staticmethod
    def _load_all_voices() -> List[Dict[str, str]]:
        """Synchronously fetch the full list of Edge-TTS voice metadata.

        The returned dicts contain keys like "ShortName" and "Gender".
        ``edge_tts.list_voices()`` is an async coroutine, so we run it inside
        ``asyncio.run`` which is safe because this is called only once per
        language and the process is not already running an event loop.
        """
        async def _list():
            return await edge_tts.list_voices()

        return asyncio.run(_list())

    @classmethod
    def _get_voices_for_lang(cls, lang: str) -> List[Dict[str, str]]:
        """Return the full voice metadata list for *lang*.
        Each entry is a dict with keys like ``ShortName`` and ``Gender``.
        The result is cached in ``_voice_cache``.
        """
        lang = lang.lower()
        if lang not in cls._voice_cache:
            all_voices = cls._load_all_voices()
            filtered = [v for v in all_voices if v["ShortName"].lower().startswith(f"{lang}-")]
            cls._voice_cache[lang] = filtered
            # Separate round‑robin counters for each gender plus a generic one
            cls._round_robin_index[lang] = {"male": 0, "female": 0, "any": 0}
        return cls._voice_cache[lang]

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------
    def get_narrator_voice(self, target_lang: str) -> Optional[str]:
        """Return a fixed, deterministic voice reserved for the Narrator.

        Prefers a male voice (a neutral narration feel) and otherwise falls back
        to the first available voice for the language. Always returns the *same*
        voice for a given language so the narrator sounds consistent.
        """
        all_voices = self._get_voices_for_lang(target_lang)
        if not all_voices:
            return None
        males = [v["ShortName"] for v in all_voices if v.get("Gender", "").lower() == "male"]
        return males[0] if males else all_voices[0]["ShortName"]

    def get_voice(self, speaker: str, target_lang: str, gender: Optional[str] = None,
                  exclude: Optional[List[str]] = None) -> Optional[str]:
        """Return a voice ID for *speaker* in *target_lang*.

        Resolution order:
        1️⃣ **Explicit map** – if ``speaker`` exists in ``self.explicit_map``
            return that voice.
        2️⃣ **Gender‑aware fallback** – if ``gender`` is ``"male"`` or ``"female"``
            pick a voice that matches the gender.
        3️⃣ **General fallback** – round‑robin over any remaining voices.

        ``exclude`` lists voice IDs that must not be auto-assigned (e.g. the voice
        reserved for the Narrator), so no character ever shares it.
        """
        # 1️⃣ Explicit mapping
        if speaker in self.explicit_map:
            return self.explicit_map[speaker]

        # Load all voice dicts for the language
        all_voices = self._get_voices_for_lang(target_lang)
        if not all_voices:
            return None

        excluded = set(exclude or [])

        # 2️⃣ Gender‑aware selection
        if gender:
            gender_key = gender.lower()
            gender_pool = [v["ShortName"] for v in all_voices
                           if v.get("Gender", "").lower() == gender_key and v["ShortName"] not in excluded]
            if gender_pool:
                idx = self._round_robin_index[target_lang].get(gender_key, 0)
                voice = gender_pool[idx % len(gender_pool)]
                self._round_robin_index[target_lang][gender_key] = (idx + 1) % len(gender_pool)
                return voice
        # 3️⃣ General fallback (any voice not excluded)
        any_pool = [v["ShortName"] for v in all_voices if v["ShortName"] not in excluded]
        if not any_pool:
            # Every voice was excluded — fall back to the full pool rather than
            # return nothing (e.g. a language with only one voice).
            any_pool = [v["ShortName"] for v in all_voices]
        idx = self._round_robin_index[target_lang].get("any", 0)
        voice = any_pool[idx % len(any_pool)]
        self._round_robin_index[target_lang]["any"] = (idx + 1) % len(any_pool)
        return voice

    # ---------------------------------------------------------------------
    # Helper for bulk creation of explicit maps from a user‑provided dict.
    # ---------------------------------------------------------------------
    @staticmethod
    def validate_explicit_map(explicit_map: Dict[str, str], target_lang: str) -> Dict[str, str]:
        """Validate that every voice ID in ``explicit_map`` exists for ``target_lang``.
        Returns a dict with only valid IDs.
        """
        all_voices = VoiceManager._get_voices_for_lang(target_lang)
        available = {v["ShortName"] for v in all_voices}
        return {speaker: vid for speaker, vid in explicit_map.items() if vid in available}

# ---------------------------------------------------------------------------
# Convenience singleton – most of the codebase will use the default manager.
# ---------------------------------------------------------------------------
default_voice_manager = VoiceManager()

def get_voice_for_speaker(speaker: str, target_lang: str, explicit_map: Optional[Dict[str, str]] = None) -> Optional[str]:
    """Utility function used by callers that may provide an ``explicit_map`` on‑the‑fly.

    If ``explicit_map`` is supplied it overrides the singleton's map for this call.
    The map is validated against the live voice list before use.
    """
    if explicit_map is not None:
        manager = VoiceManager(VoiceManager.validate_explicit_map(explicit_map, target_lang))
    else:
        manager = default_voice_manager
    return manager.get_voice(speaker, target_lang)
