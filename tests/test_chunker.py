import unittest
from basha.pipeline.chunker import split_text_into_chunks

class TestChunker(unittest.TestCase):
    def test_empty_and_whitespace_text(self):
        self.assertEqual(split_text_into_chunks(""), [])
        self.assertEqual(split_text_into_chunks("   \n  \t "), [])

    def test_simple_sentence_splitting(self):
        text = "Hello world. This is a sentence! Is it working? Yes."
        chunks = split_text_into_chunks(text, max_chars=50)
        # Should split on sentences nicely and group them under 50 characters
        for chunk in chunks:
            self.assertTrue(len(chunk) <= 50)
        self.assertIn("Hello world.", chunks[0])

    def test_clause_splitting(self):
        text = "Although it was raining, we went for a walk; it was refreshing, but cold."
        chunks = split_text_into_chunks(text, max_chars=40)
        for chunk in chunks:
            self.assertTrue(len(chunk) <= 40)

    def test_single_long_word(self):
        # A single word longer than max_chars should not cause an infinite loop
        long_word = "a" * 100
        chunks = split_text_into_chunks(long_word, max_chars=50)
        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0], "a" * 50)
        self.assertEqual(chunks[1], "a" * 50)

    def test_exact_limit_boundary(self):
        # 10 chars sentence
        text = "123456789. 123456789."
        chunks = split_text_into_chunks(text, max_chars=10)
        self.assertEqual(chunks, ["123456789.", "123456789."])
