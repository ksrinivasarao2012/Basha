"""
Local CPU-only TRANSLATION quality benchmark for Basha.

This measures the translation your app ACTUALLY uses (deep-translator / Google
Translate) against human "gold" reference translations from the FLORES set,
using the standard machine-translation metrics:

    chrF  (character-level)  <- main metric, fair for Indian languages
    BLEU  (word-level)       <- secondary, the classic metric

Both run 0-100, higher = better.

Runs 100% on your laptop CPU. The only network use is the translation calls
themselves (small text requests). No GPU, no model download, no Colab.

Needs the gold-answer file `flores_evaluation_set.json` (download it from your
Colab) in the project root. Each row looks like:
    {"en": "...", "te": "...", "ta": "...", "kn": "...",
     "ml": "...", "mr": "...", "hi": "..."}

Usage
-----
    python scripts/translation_eval.py                 # default: 25 sentences
    python scripts/translation_eval.py --sample 40 --langs te hi de
"""

import argparse
import csv
import json
import os
import sys
import time

import sacrebleu

from basha.translation.deep_translator_backend import DeepTranslatorBackend

# Print Indic text to the Windows console without crashing.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

GOLD_FILE = "flores_evaluation_set.json"
OUT_DIR = "eval_output"
RESULTS_CSV = os.path.join(OUT_DIR, "translation_scores.csv")
PRED_CSV = os.path.join(OUT_DIR, "translation_predictions.csv")

# Indian languages present in the FLORES gold file.
DEFAULT_LANGS = ["te", "hi", "ta", "kn", "ml", "mr"]


def _clean(s):
    return s.strip().strip('"').strip() if isinstance(s, str) else ""


def main():
    p = argparse.ArgumentParser(description="Local translation quality benchmark (chrF/BLEU).")
    p.add_argument("--sample", type=int, default=25,
                   help="How many sentences to test (smaller = faster, avoids rate-limits).")
    p.add_argument("--langs", nargs="+", default=DEFAULT_LANGS)
    p.add_argument("--delay", type=float, default=0.3,
                   help="Seconds to wait between calls (polite to the free translator).")
    args = p.parse_args()

    if not os.path.exists(GOLD_FILE):
        print(f"ERROR: gold file '{GOLD_FILE}' not found in {os.getcwd()}.")
        print("Download 'flores_evaluation_set.json' from your Colab and put it here.")
        return

    with open(GOLD_FILE, encoding="utf-8") as f:
        data = json.load(f)

    rows = data[: args.sample]
    src = [_clean(r["en"]) for r in rows]
    print(f"Loaded {len(src)} English sentences from {GOLD_FILE}.")
    print(f"Testing languages: {args.langs}\n")

    os.makedirs(OUT_DIR, exist_ok=True)
    translator = DeepTranslatorBackend()

    score_rows = []
    pred_rows = []

    print(f"{'lang':6s} {'chrF':>7s} {'BLEU':>7s} {'n':>4s}")
    print("-" * 28)

    for lang in args.langs:
        # Skip a language if the gold file doesn't have it.
        if lang not in rows[0]:
            print(f"{lang:6s}  (no gold references in file — skipped)")
            continue

        refs = [_clean(r[lang]) for r in rows]
        hyps = []
        for i, sentence in enumerate(src):
            try:
                hyps.append(translator.translate(sentence, lang))
            except Exception as e:
                print(f"  ! translate failed [{lang}] sentence {i}: {e}")
                hyps.append("")
            time.sleep(args.delay)

        chrf = sacrebleu.corpus_chrf(hyps, [refs]).score
        bleu = sacrebleu.corpus_bleu(hyps, [refs]).score
        print(f"{lang:6s} {chrf:7.2f} {bleu:7.2f} {len(src):4d}")

        score_rows.append({"lang": lang, "chrF": round(chrf, 2),
                           "BLEU": round(bleu, 2), "n": len(src)})
        for s, h, ref in zip(src, hyps, refs):
            pred_rows.append({"lang": lang, "english": s, "app_translation": h, "gold": ref})

    if not score_rows:
        print("\nNo languages scored — check the gold file's keys.")
        return

    with open(RESULTS_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["lang", "chrF", "BLEU", "n"])
        w.writeheader()
        w.writerows(score_rows)
    with open(PRED_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["lang", "english", "app_translation", "gold"])
        w.writeheader()
        w.writerows(pred_rows)

    avg_chrf = sum(r["chrF"] for r in score_rows) / len(score_rows)
    print("-" * 28)
    print(f"{'AVG':6s} {avg_chrf:7.2f}")
    print(f"\nScores written to       {RESULTS_CSV}")
    print(f"Side-by-side examples   {PRED_CSV}")
    print("\nReading: chrF is the headline number. 50+ is strong, 40-50 decent, "
          "below 35 weak. BLEU is the stricter secondary metric.")


if __name__ == "__main__":
    main()
