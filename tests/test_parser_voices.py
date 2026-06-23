"""Unit tests for the dialogue script parser and the Edge-TTS VoiceManager.

These are pure-logic tests: the parser does no I/O, and the voice list is
mocked so the suite runs fully offline and CPU-only (no network call to the
Edge-TTS voice catalogue).
"""

from unittest.mock import patch

import pytest

from basha.script.parser import parse_script
from basha.tts.voices import VoiceManager


# ---------------------------------------------------------------------------
# Dialogue script parser
# ---------------------------------------------------------------------------
class TestParseScript:
    def test_standard_speaker_lines(self):
        script = "Ravi: Hello there\nMeena: Hi Ravi"
        mapping = {"Ravi": "hi-IN-MadhavNeural", "Meena": "hi-IN-SwaraNeural"}
        result = parse_script(script, mapping)
        assert result == [
            ("Hello there", "hi-IN-MadhavNeural"),
            ("Hi Ravi", "hi-IN-SwaraNeural"),
        ]

    def test_line_without_colon_is_narration(self):
        # No colon -> whole line is the utterance, voice is None (default voice).
        result = parse_script("Just a plain narration line")
        assert result == [("Just a plain narration line", None)]

    def test_blank_and_whitespace_lines_are_ignored(self):
        script = "Ravi: First\n\n   \n\t\nMeena: Second"
        result = parse_script(script)
        # Two real turns; the empty/whitespace lines drop out.
        assert len(result) == 2
        assert result[0][0] == "First"
        assert result[1][0] == "Second"

    def test_speaker_and_utterance_are_stripped(self):
        script = "   Ravi   :    Hello world   "
        mapping = {"Ravi": "v1"}
        result = parse_script(script, mapping)
        # Speaker name is stripped before the mapping lookup, utterance is stripped.
        assert result == [("Hello world", "v1")]

    def test_unmapped_speaker_gets_none_voice(self):
        result = parse_script("Ravi: Hello", voice_mapping={"Meena": "v2"})
        assert result == [("Hello", None)]


# ---------------------------------------------------------------------------
# VoiceManager
# ---------------------------------------------------------------------------
MOCK_VOICES = [
    {"ShortName": "en-US-JennyNeural", "Gender": "Female"},
    {"ShortName": "en-US-GuyNeural", "Gender": "Male"},
    {"ShortName": "hi-IN-MadhavNeural", "Gender": "Male"},
    {"ShortName": "hi-IN-SwaraNeural", "Gender": "Female"},
]


@pytest.fixture(autouse=True)
def fresh_voice_caches():
    """Reset the class-level caches and stub the live voice catalogue.

    VoiceManager caches voices and round-robin counters on the *class*, so they
    leak across tests unless cleared. We also patch the network fetch so no
    request to Edge-TTS is ever made.
    """
    VoiceManager._voice_cache.clear()
    VoiceManager._round_robin_index.clear()
    with patch.object(VoiceManager, "_load_all_voices", return_value=MOCK_VOICES):
        yield
    VoiceManager._voice_cache.clear()
    VoiceManager._round_robin_index.clear()


class TestVoiceManager:
    def test_explicit_map_takes_precedence(self):
        vm = VoiceManager(explicit_map={"Ravi": "hi-IN-MadhavNeural"})
        assert vm.get_voice("Ravi", "hi") == "hi-IN-MadhavNeural"

    def test_gender_aware_male(self):
        vm = VoiceManager()
        assert vm.get_voice("__single__", "hi", gender="male") == "hi-IN-MadhavNeural"

    def test_gender_aware_female(self):
        vm = VoiceManager()
        assert vm.get_voice("__single__", "hi", gender="female") == "hi-IN-SwaraNeural"

    def test_round_robin_rotates_and_wraps(self):
        vm = VoiceManager()
        # Hindi has two voices; unnamed speakers should cycle through both, then wrap.
        first = vm.get_voice("A", "hi")
        second = vm.get_voice("B", "hi")
        third = vm.get_voice("C", "hi")
        assert first != second          # two distinct speakers -> two distinct voices
        assert third == first           # third wraps back to the first voice

    def test_unsupported_language_returns_none(self):
        vm = VoiceManager()
        assert vm.get_voice("A", "xyz") is None

    def test_validate_explicit_map_drops_invalid_ids(self):
        explicit = {
            "Ravi": "hi-IN-MadhavNeural",   # valid
            "Ghost": "hi-IN-DoesNotExist",  # invalid -> dropped
        }
        validated = VoiceManager.validate_explicit_map(explicit, "hi")
        assert validated == {"Ravi": "hi-IN-MadhavNeural"}
