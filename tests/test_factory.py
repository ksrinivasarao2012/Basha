import os
import unittest
from unittest.mock import patch
from basha.core.config import settings
from basha.tts.factory import TTSFactory
from basha.tts.gtts_backend import GTTSBackend
from basha.tts.sarvam import SarvamBackend

class TestTTSFactory(unittest.TestCase):
    def test_factory_resolves_gtts_explicitly(self):
        backend = TTSFactory.get_backend("gtts")
        self.assertIsInstance(backend, GTTSBackend)

    def test_factory_resolves_sarvam_explicitly(self):
        # Even without key, resolving explicitly returns SarvamBackend
        # but initializing/using it might check the key
        backend = TTSFactory.get_backend("sarvam")
        self.assertIsInstance(backend, SarvamBackend)

    def test_factory_resolves_auto_fallback_without_key(self):
        with patch.object(settings, "sarvam_api_key", ""):
            # Hindi is an Indian language, but API key is missing -> fallback to GTTS
            backend = TTSFactory.get_backend("auto", lang="hi")
            self.assertIsInstance(backend, GTTSBackend)

    def test_factory_resolves_auto_with_key_for_indian_lang(self):
        with patch.object(settings, "sarvam_api_key", "mock-key"):
            # Telugu with API key -> Sarvam
            backend = TTSFactory.get_backend("auto", lang="te")
            self.assertIsInstance(backend, SarvamBackend)

    def test_factory_resolves_auto_with_key_for_non_indian_lang(self):
        with patch.object(settings, "sarvam_api_key", "mock-key"):
            # German (de) with API key -> fallback to GTTS because not supported by Sarvam
            backend = TTSFactory.get_backend("auto", lang="de")
            self.assertIsInstance(backend, GTTSBackend)
