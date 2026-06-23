import re
import unicodedata
from typing import Sequence, Any


def normalize_text(s: str) -> str:
    """Normalize text for fair CER/WER comparison.

    - Unicode NFC (so the same character is encoded identically)
    - strip punctuation (Unicode category starting with 'P') — keeps letters
      AND Indic combining vowel signs (category M), which we must NOT remove
    - lowercase (helps European languages; a no-op for Indic scripts)
    - collapse whitespace

    Without this, a perfectly-pronounced sentence scores as "wrong" just because
    the ASR dropped a comma or returned a different capitalization.
    """
    if not s:
        return ""
    s = unicodedata.normalize("NFC", s)
    s = "".join(ch for ch in s if not unicodedata.category(ch).startswith("P"))
    s = s.lower()
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _levenshtein_distance(seq1: Sequence[Any], seq2: Sequence[Any]) -> int:
    """
    Computes the Levenshtein distance between two sequences.
    """
    if len(seq1) < len(seq2):
        return _levenshtein_distance(seq2, seq1)
    if len(seq2) == 0:
        return len(seq1)
    
    previous_row = list(range(len(seq2) + 1))
    for i, item1 in enumerate(seq1):
        current_row = [i + 1]
        for j, item2 in enumerate(seq2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (item1 != item2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
        
    return previous_row[-1]

def calculate_cer(reference: str, hypothesis: str) -> float:
    """
    Computes Character Error Rate (CER) on normalized text.
    """
    ref = normalize_text(reference)
    hyp = normalize_text(hypothesis)
    if not ref:
        return 0.0 if not hyp else 1.0

    distance = _levenshtein_distance(ref, hyp)
    return float(distance) / len(ref)

def calculate_wer(reference: str, hypothesis: str) -> float:
    """
    Computes Word Error Rate (WER) on normalized text.
    """
    ref_words = normalize_text(reference).split()
    hyp_words = normalize_text(hypothesis).split()
    if not ref_words:
        return 0.0 if not hyp_words else 1.0

    distance = _levenshtein_distance(ref_words, hyp_words)
    return float(distance) / len(ref_words)

def calculate_rtf(synthesis_time: float, audio_duration: float) -> float:
    """
    Computes Real-Time Factor (RTF).
    RTF = synthesis_time / audio_duration
    """
    if audio_duration <= 0:
        return 0.0
    return float(synthesis_time) / float(audio_duration)

_similarity_model = None

def calculate_semantic_similarity(reference: str, hypothesis: str) -> float:
    """
    Computes semantic similarity (cosine similarity of embeddings) between
    reference and hypothesis text using paraphrase-multilingual-MiniLM-L12-v2.
    """
    global _similarity_model
    if not reference or not hypothesis:
        return 0.0
    
    try:
        if _similarity_model is None:
            from sentence_transformers import SentenceTransformer
            _similarity_model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
            
        emb1 = _similarity_model.encode(reference, convert_to_tensor=True)
        emb2 = _similarity_model.encode(hypothesis, convert_to_tensor=True)
        
        from sentence_transformers.util import cos_sim
        sim = cos_sim(emb1, emb2).item()
        return round(float(sim), 4)
    except Exception as e:
        # Fallback to a basic string match indicator or return 0.0 if imports/loading fail
        return 0.0


