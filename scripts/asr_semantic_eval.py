import os
import sys
import json
import csv
import time
import io
import argparse
from typing import List

from pydub import AudioSegment

from basha.tts.factory import TTSFactory
from basha.eval.metrics import calculate_rtf, calculate_semantic_similarity
from basha.eval.asr_roundtrip import transcribe_audio_bytes, ASRRateLimited

# Configure stdout encoding to print non-ASCII characters on Windows without crashing.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

GOLD_FILE = "flores_evaluation_set.json"
OUT_DIR = "eval_output"
RESULTS_CSV = os.path.join(OUT_DIR, "asr_semantic_scores.csv")


def _clean(s):
    return s.strip().strip('"').strip() if isinstance(s, str) else ""


def main():
    p = argparse.ArgumentParser(description="Evaluate synthesized speech against FLORES references using multilingual BERT similarity.")
    p.add_argument("--langs", nargs="+", default=["hi", "te", "de"], help="Languages to evaluate")
    p.add_argument("--sample", type=int, default=10, help="Number of sentences per language to evaluate")
    p.add_argument("--delay", type=float, default=1.0, help="Delay in seconds between external API calls (to avoid rate limits)")
    args = p.parse_args()

    if not os.path.exists(GOLD_FILE):
        print(f"ERROR: Gold reference file '{GOLD_FILE}' not found in the current working directory.")
        print("Please copy it from 'samples/input/flores_evaluation_set.json' to the root directory first.")
        return

    with open(GOLD_FILE, encoding="utf-8") as f:
        data = json.load(f)

    rows = data[:args.sample]
    print(f"Loaded {args.sample} evaluation sentences from '{GOLD_FILE}'.")
    print(f"Target languages: {args.langs}\n")

    os.makedirs(OUT_DIR, exist_ok=True)
    summary_data = []

    print(f"{'lang':6s} | {'success %':>9s} | {'avg similarity':>14s} | {'avg RTF':>7s}")
    print("-" * 55)

    for lang in args.langs:
        # Check if the target language exists in the FLORES dataset
        if not rows or lang not in rows[0]:
            print(f"{lang:6s} | (language not found in gold references — skipped)")
            continue

        sentences = [_clean(r[lang]) for r in rows if r.get(lang)]
        engine = TTSFactory.get_backend("auto", lang=lang)
        backend_name = engine.__class__.__name__

        success_count = 0
        total_similarity = 0.0
        total_rtf = 0.0
        processed_count = 0

        for i, gold_text in enumerate(sentences):
            if not gold_text:
                continue

            time.sleep(args.delay)
            t_start = time.perf_counter()
            audio_bytes = b""
            transcription = ""

            try:
                # 1. Synthesize target-language gold text to audio
                audio_bytes = engine.synthesize(gold_text, lang=lang)
                synth_time = time.perf_counter() - t_start

                if not audio_bytes:
                    print(f"  ! [{lang}] Sentence {i+1}: Synthesized empty audio bytes.")
                    continue

                # Get audio duration
                audio_segment = AudioSegment.from_file(io.BytesIO(audio_bytes))
                duration = len(audio_segment) / 1000.0  # seconds

                rtf = calculate_rtf(synth_time, duration)
                total_rtf += rtf

                time.sleep(args.delay)
                # 2. Transcribe audio back to text via ASR
                transcription = transcribe_audio_bytes(audio_bytes, lang=lang)

                if transcription:
                    # 3. Calculate semantic similarity between transcription and gold text
                    similarity = calculate_semantic_similarity(gold_text, transcription)
                    total_similarity += similarity
                    success_count += 1
                else:
                    similarity = 0.0
                    print(f"  ! [{lang}] Sentence {i+1}: ASR returned empty transcription (unintelligible or rate-limited).")

                processed_count += 1
                summary_data.append({
                    "language": lang,
                    "backend": backend_name,
                    "sentence_idx": i,
                    "gold_reference": gold_text,
                    "asr_transcription": transcription,
                    "semantic_similarity": round(similarity, 4),
                    "rtf": round(rtf, 4),
                    "audio_duration_seconds": round(duration, 2)
                })

            except ASRRateLimited as e:
                print(f"  ! [{lang}] Sentence {i+1}: ASR Rate-limited: {e}")
            except Exception as e:
                print(f"  ! [{lang}] Sentence {i+1}: Error: {e}")

        # Compute averages
        avg_similarity = (total_similarity / success_count) if success_count > 0 else 0.0
        avg_rtf = (total_rtf / processed_count) if processed_count > 0 else 0.0
        success_pct = (success_count / len(sentences)) * 100 if sentences else 0.0

        print(f"{lang:6s} | {success_pct:8.1f}% | {avg_similarity:14.4f} | {avg_rtf:7.3f}")

    if summary_data:
        with open(RESULTS_CSV, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(summary_data[0].keys()))
            w.writeheader()
            w.writerows(summary_data)
        print(f"\nDetailed evaluation results written to: {RESULTS_CSV}")


if __name__ == "__main__":
    main()
