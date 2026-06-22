import json
import time
import os
import io
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pydub import AudioSegment

# Add src/ to PYTHONPATH programmatically
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from basha.pipeline.orchestrator import PipelineOrchestrator
from basha.eval.metrics import calculate_cer, calculate_wer, calculate_rtf
from basha.eval.asr_roundtrip import transcribe_audio_bytes

# The 6 Indian regional languages supported by Sarvam AI
INDIAN_LANGUAGES = {
    "te": "Telugu",
    "ta": "Tamil",
    "kn": "Kannada",
    "ml": "Malayalam",
    "mr": "Marathi",
    "hi": "Hindi"
}

lock = threading.Lock()

def evaluate_sentence_backend(orchestrator: PipelineOrchestrator, idx: int, en_text: str, ref_translation: str, lang_code: str, backend: str):
    """
    Evaluates a single sentence for a specific backend: translates, synthesizes, transcribes, and calculates metrics.
    """
    try:
        start_time = time.perf_counter()
        # Synthesize audio with target backend
        audio_bytes = orchestrator.process(en_text, lang_code, backend=backend)
        synthesis_time = time.perf_counter() - start_time
        
        if not audio_bytes:
            return None
            
        audio_segment = AudioSegment.from_file(io.BytesIO(audio_bytes))
        audio_duration = len(audio_segment) / 1000.0
        
        # Transcribe via ASR
        transcription = transcribe_audio_bytes(audio_bytes, lang=lang_code)
        
        # Calculate metrics
        cer = calculate_cer(ref_translation.lower(), transcription.lower())
        wer = calculate_wer(ref_translation.lower(), transcription.lower())
        rtf = calculate_rtf(synthesis_time, audio_duration)
        
        return {
            "sentence_id": idx,
            "cer": cer,
            "wer": wer,
            "rtf": rtf
        }
    except Exception as e:
        return None

def main():
    json_path = "samples/input/flores_evaluation_set.json"
    if not os.path.exists(json_path):
        print(f"Error: {json_path} not found. Please run download_flores.py first.")
        sys.exit(1)
        
    with open(json_path, "r", encoding="utf-8") as f:
        eval_set = json.load(f)
        
    # Limit to top 20 sentences
    eval_set = eval_set[:20]
    total_sentences = len(eval_set)
    print(f"Loaded top {total_sentences} parallel sentences.")
    print("Preparing comparison benchmark for 6 Indian regional languages...")
    print("Backends: gtts vs sarvam")
    
    # Run with exactly 4 workers (4 cores)
    max_workers = 4
    print(f"Running with {max_workers} concurrent threads.")
    
    orchestrator = PipelineOrchestrator()
    results = {}

    for lang_code, lang_name in INDIAN_LANGUAGES.items():
        results[lang_code] = {
            "language_name": lang_name,
            "gtts": {"total_cer": 0.0, "total_wer": 0.0, "total_rtf": 0.0, "count": 0},
            "sarvam": {"total_cer": 0.0, "total_wer": 0.0, "total_rtf": 0.0, "count": 0}
        }
        
        for backend in ["gtts", "sarvam"]:
            print(f"\nEvaluating '{lang_name}' ({lang_code}) using backend: {backend}...")
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {
                    executor.submit(
                        evaluate_sentence_backend,
                        orchestrator,
                        idx,
                        eval_set[idx]["en"],
                        eval_set[idx][lang_code],
                        lang_code,
                        backend
                    ): idx
                    for idx in range(total_sentences)
                }
                
                completed_count = 0
                for future in as_completed(futures):
                    res = future.result()
                    completed_count += 1
                    print(f"  [{backend.upper()}] Progress: {completed_count}/{total_sentences}...", end="\r", flush=True)
                    
                    if res:
                        results[lang_code][backend]["total_cer"] += res["cer"]
                        results[lang_code][backend]["total_wer"] += res["wer"]
                        results[lang_code][backend]["total_rtf"] += res["rtf"]
                        results[lang_code][backend]["count"] += 1

    # Print & Save Report
    report_lines = [
        "# TTS Backend Comparison Report (Top 20 Sentences)",
        f"Generated on: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Workers used: {max_workers} concurrent threads",
        "",
        "| Language | Backend | Avg CER | Avg WER | Avg RTF |",
        "|---|---|---|---|---|",
    ]
    
    print("\n\n" + "=" * 70)
    print(" COMPARISON RESULTS SUMMARY (Top 20 Sentences)")
    print("=" * 70)
    print(f"| Language | Backend | Avg CER | Avg WER | Avg RTF |")
    print(f"|---|---|---|---|---|")
    
    for lang_code, data in results.items():
        for backend in ["gtts", "sarvam"]:
            stats = data[backend]
            count = stats["count"]
            if count > 0:
                avg_cer = f"{(stats['total_cer'] / count) * 100:.2f}%"
                avg_wer = f"{(stats['total_wer'] / count) * 100:.2f}%"
                avg_rtf = f"{stats['total_rtf'] / count:.4f}"
            else:
                avg_cer, avg_wer, avg_rtf = "N/A", "N/A", "N/A"
                
            row = f"| {data['language_name']} | {backend.upper()} | {avg_cer} | {avg_wer} | {avg_rtf} |"
            print(row)
            report_lines.append(row)
            
    print("=" * 70)
    
    # Save comparison report
    report_path = "samples/output/comparison_report.md"
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))
    print(f"Saved comparison report to {report_path}")

if __name__ == "__main__":
    main()
