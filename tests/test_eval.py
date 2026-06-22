import time
import pytest
from basha.eval.metrics import calculate_cer, calculate_wer, calculate_rtf
from basha.eval.asr_roundtrip import transcribe_audio_bytes
from basha.tts.gtts_backend import GTTSBackend
from pydub import AudioSegment
import io

def test_metrics_calculation():
    # 1. CER Tests
    assert calculate_cer("hello", "hello") == 0.0
    assert calculate_cer("hello", "hell") == 0.2  # 1 deletion
    assert calculate_cer("hello", "hello world") == 1.2  # 6 insertions
    assert calculate_cer("hello", "hallo") == 0.2  # 1 substitution
    assert calculate_cer("", "") == 0.0
    assert calculate_cer("", "hello") == 1.0

    # 2. WER Tests
    assert calculate_wer("hello world", "hello world") == 0.0
    assert calculate_wer("hello world", "hello") == 0.5  # 1 deletion
    assert calculate_wer("hello world", "hello beautiful world") == 0.5  # 1 insertion
    assert calculate_wer("hello world", "hallo world") == 0.5  # 1 substitution
    assert calculate_wer("", "") == 0.0
    assert calculate_wer("", "hello") == 1.0

    # 3. RTF Tests
    assert calculate_rtf(5.0, 10.0) == 0.5
    assert calculate_rtf(2.0, 0.0) == 0.0

def test_asr_roundtrip_evaluation():
    # Test text to synthesize
    original_text = "welcome to the test suite"
    
    # Synthesize using GTTS
    tts = GTTSBackend()
    start_time = time.perf_counter()
    audio_bytes = tts.synthesize(original_text, lang="en")
    synthesis_time = time.perf_counter() - start_time
    
    assert len(audio_bytes) > 0
    
    # Get audio duration
    audio_segment = AudioSegment.from_file(io.BytesIO(audio_bytes))
    audio_duration = len(audio_segment) / 1000.0  # seconds
    
    # Calculate RTF
    rtf = calculate_rtf(synthesis_time, audio_duration)
    assert rtf >= 0
    
    # Transcribe back using ASR
    try:
        transcription = transcribe_audio_bytes(audio_bytes, lang="en")
    except Exception as e:
        pytest.skip(f"Skipping network dependent ASR call: {e}")
        return
        
    print(f"Original: {original_text}")
    print(f"Transcribed: {transcription}")
    
    # Calculate error rates
    cer = calculate_cer(original_text.lower(), transcription.lower())
    wer = calculate_wer(original_text.lower(), transcription.lower())
    
    # The transcription might not be perfectly identical but should be close
    # We assert that CER is under 30% for intelligibility
    assert cer <= 0.3
    assert wer <= 0.5
