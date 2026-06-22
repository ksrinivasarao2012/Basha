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

# The 11 languages supported by Basha
LANGUAGES = {
    "te": "Telugu",
    "ta": "Tamil",
    "kn": "Kannada",
    "ml": "Malayalam",
    "mr": "Marathi",
    "hi": "Hindi",
    "de": "German",
    "fr": "French",
    "es": "Spanish",
    "it": "Italian",
    "pt": "Portuguese"
}

# Thread lock for safe file writing and console output printing
lock = threading.Lock()

def evaluate_single_sentence(orchestrator: PipelineOrchestrator, idx: int, en_text: str, ref_translation: str, lang_code: str):
    """
    Evaluates a single sentence: translates, synthesizes, transcribes, and calculates metrics.
    """
    try:
        # 1. Measure synthesis time
        start_time = time.perf_counter()
        audio_bytes = orchestrator.process(en_text, lang_code)
        synthesis_time = time.perf_counter() - start_time
        
        if not audio_bytes:
            return None
            
        # 2. Get audio duration
        audio_segment = AudioSegment.from_file(io.BytesIO(audio_bytes))
        audio_duration = len(audio_segment) / 1000.0
        
        # 3. Transcribe via ASR
        transcription = transcribe_audio_bytes(audio_bytes, lang=lang_code)
        
        # 4. Calculate metrics
        cer = calculate_cer(ref_translation.lower(), transcription.lower())
        wer = calculate_wer(ref_translation.lower(), transcription.lower())
        rtf = calculate_rtf(synthesis_time, audio_duration)
        
        return {
            "sentence_id": idx,
            "cer": cer,
            "wer": wer,
            "rtf": rtf
        }
    except Exception:
        # Return None if it fails
        return None

def main():
    json_path = "samples/input/flores_evaluation_set.json"
    if not os.path.exists(json_path):
        print(f"Error: {json_path} not found. Please run download_flores.py first.")
        sys.exit(1)
        
    with open(json_path, "r", encoding="utf-8") as f:
        eval_set = json.load(f)
        
    total_sentences = len(eval_set)
    print(f"Loaded {total_sentences} parallel sentences.")
    print("Preparing parallel evaluation for all 11 languages...")
    
    # 6 concurrent threads is a fast parallel balance
    max_workers = 6
    print(f"Running with {max_workers} concurrent threads.")
    print("Note: You can press Ctrl+C to stop and save progress.\n")
    
    orchestrator = PipelineOrchestrator()
    report_path = "samples/output/evaluation_report.json"
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    
    # Load progress
    progress_data = {}
    if os.path.exists(report_path):
        try:
            with open(report_path, "r", encoding="utf-8") as f:
                progress_data = json.load(f)
            print(f"Loaded existing progress from {report_path}")
        except Exception:
            pass

    try:
        for lang_code, lang_name in LANGUAGES.items():
            if lang_code not in progress_data:
                progress_data[lang_code] = {
                    "language_name": lang_name,
                    "sentences_evaluated": 0,
                    "total_cer": 0.0,
                    "total_wer": 0.0,
                    "total_rtf": 0.0,
                    "details": []
                }
            
            lang_progress = progress_data[lang_code]
            start_idx = lang_progress["sentences_evaluated"]
            
            if start_idx >= total_sentences:
                print(f"Language '{lang_name}' already fully evaluated.")
                continue
                
            print(f"\nEvaluating '{lang_name}' ({lang_code}) in parallel from index {start_idx}...")
            
            # Run sentences in parallel
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {
                    executor.submit(
                        evaluate_single_sentence,
                        orchestrator,
                        idx,
                        eval_set[idx]["en"],
                        eval_set[idx][lang_code],
                        lang_code
                    ): idx
                    for idx in range(start_idx, total_sentences)
                }
                
                completed_count = start_idx
                for future in as_completed(futures):
                    result = future.result()
                    
                    with lock:
                        completed_count += 1
                        print(f"  [{lang_name}] Progress: {completed_count}/{total_sentences}...", end="\r", flush=True)
                        
                        if result:
                            lang_progress["total_cer"] += result["cer"]
                            lang_progress["total_wer"] += result["wer"]
                            lang_progress["total_rtf"] += result["rtf"]
                            lang_progress["sentences_evaluated"] += 1
                            lang_progress["details"].append(result)
                            
                        # Save progress files periodically
                        if completed_count % 5 == 0:
                            with open(report_path, "w", encoding="utf-8") as f:
                                json.dump(progress_data, f, ensure_ascii=False, indent=2)

            # Final save for the completed language
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(progress_data, f, ensure_ascii=False, indent=2)
                
            se = lang_progress["sentences_evaluated"]
            if se > 0:
                avg_cer = (lang_progress["total_cer"] / se) * 100
                avg_wer = (lang_progress["total_wer"] / se) * 100
                avg_rtf = lang_progress["total_rtf"] / se
                print(f"\nCompleted '{lang_name}' -> Avg CER: {avg_cer:.2f}%, Avg WER: {avg_wer:.2f}%, Avg RTF: {avg_rtf:.4f}")

    except KeyboardInterrupt:
        print("\nEvaluation paused by user. Saving current progress...")
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(progress_data, f, ensure_ascii=False, indent=2)
        print(f"Progress saved to {report_path}")
        sys.exit(0)

    # Generate final Markdown Summary
    print("\n" + "=" * 70)
    print(" FINAL EVALUATION SUMMARY REPORT")
    print("=" * 70)
    print(f"| Language | Evaluated Sentences | Avg CER | Avg WER | Avg RTF |")
    print(f"|---|---|---|---|---|")
    
    markdown_lines = [
        "# Multilingual Speech Evaluation Report",
        f"Generated on: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "| Language | Evaluated Sentences | Avg CER | Avg WER | Avg RTF |",
        "|---|---|---|---|---|",
    ]
    
    for lang_code, data in progress_data.items():
        se = data["sentences_evaluated"]
        if se > 0:
            cer_pct = f"{(data['total_cer'] / se) * 100:.2f}%"
            wer_pct = f"{(data['total_wer'] / se) * 100:.2f}%"
            rtf_val = f"{data['total_rtf'] / se:.4f}"
            row = f"| {data['language_name']} | {se}/{total_sentences} | {cer_pct} | {wer_pct} | {rtf_val} |"
            print(row)
            markdown_lines.append(row)
            
    # Save markdown report
    md_report_path = "samples/output/evaluation_report.md"
    with open(md_report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(markdown_lines))
    print("=" * 70)
    print(f"Saved markdown report to {md_report_path}")

if __name__ == "__main__":
    main()
