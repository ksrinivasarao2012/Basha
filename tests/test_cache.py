import os
import unittest
import tempfile
import shutil
from basha.core.cache import AudioCache

class TestAudioCache(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.cache = AudioCache(cache_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_cache_set_and_get(self):
        text = "Hello world"
        lang = "en"
        data = b"audio-bytes-data"
        
        self.cache.set(text, lang, data, backend="GTTSBackend")
        retrieved = self.cache.get(text, lang, backend="GTTSBackend")
        self.assertEqual(retrieved, data)

    def test_cache_miss(self):
        retrieved = self.cache.get("Not cached text", "en")
        self.assertIsNone(retrieved)

    def test_cache_collision_prevention_by_backend(self):
        text = "Namaste"
        lang = "hi"
        data_gtts = b"gtts-audio"
        data_sarvam = b"sarvam-audio"

        self.cache.set(text, lang, data_gtts, backend="GTTSBackend")
        self.cache.set(text, lang, data_sarvam, backend="SarvamBackend")

        # Verify we get the backend-specific cache
        self.assertEqual(self.cache.get(text, lang, backend="GTTSBackend"), data_gtts)
        self.assertEqual(self.cache.get(text, lang, backend="SarvamBackend"), data_sarvam)
