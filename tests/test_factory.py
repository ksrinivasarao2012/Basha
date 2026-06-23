import os
import unittest
from basha.tts.factory import TTSFactory
from basha.tts.gtts_backend import GTTSBackend
from basha.tts.edge_tts import EdgeTTSBackend

class TestTTSFactory(unittest.TestCase):
    def test_factory_resolves_gtts_explicitly(self):
        backend = TTSFactory.get_backend("gtts")
        self.assertIsInstance(backend, GTTSBackend)

    def test_factory_resolves_edge_explicitly(self):
        backend = TTSFactory.get_backend("edge")
        self.assertIsInstance(backend, EdgeTTSBackend)

    def test_factory_resolves_auto(self):
        backend = TTSFactory.get_backend("auto", lang="hi")
        self.assertIsInstance(backend, GTTSBackend)

