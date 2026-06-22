"""
Local CPU-only TTS evaluation for Basha.

This is the piece CER/WER and BLEU physically cannot measure: how NATURAL the
voice sounds. The only valid way to measure that is MOS (Mean Opinion Score) —
a human listens and rates naturalness 1-5. This script automates everything
around that human judgement.

Two modes
---------
1) generate : translate + synthesize a fixed sentence set with each backend,
              save the clips, and AUTOMATICALLY measure the objective stats
              (synthesis time, audio duration, RTF, file size). It also writes a
              blank rating sheet for you to fill in by ear.

2) score    : read the rating sheet you filled in (naturalness + intelligibility,
              each 1-5) and print the averaged MOS per backend and per language,
              merged with the objective RTF numbers.

Runs 100% on CPU. The only network use is the TTS calls themselves (tiny).

Usage
-----
    python scripts/tts_eval.py generate                 # default set
    python scripts/tts_eval.py generate --langs te hi de --backends gtts edge
    # ... open eval_output/tts_rating_sheet.csv, listen to each clip, fill 1-5 ...
    python scripts/tts_eval.py score
"""

import argparse
import csv
import io
import json
import os
import sys
import time
from collections import defaultdict

from pydub import AudioSegment

from basha.tts.factory import TTSFactory
from basha.translation.deep_translator_backend import DeepTranslatorBackend

try:
    sys.stdout.reconfigure(encoding="utf-8")  # print Indic text on Windows safely
except Exception:
    pass

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
OUT_DIR = "eval_output"
CLIP_DIR = os.path.join(OUT_DIR, "tts_samples")
OBJECTIVE_CSV = os.path.join(OUT_DIR, "tts_objective.csv")
RATING_CSV = os.path.join(OUT_DIR, "tts_rating_sheet.csv")

# A few neutral sentences. Short so CPU + slow internet stay fast.
SENTENCES = [
    "The train to the city leaves early tomorrow morning.",
    "She smiled and said that everything would be alright.",
    "Please remember to close the door when you leave.",
]

DEFAULT_LANGS = ["te", "hi", "de"]
DEFAULT_BACKENDS = ["gtts", "edge"]


# ---------------------------------------------------------------------------
# generate
# ---------------------------------------------------------------------------
def generate(langs, backends):
    os.makedirs(CLIP_DIR, exist_ok=True)
    translator = DeepTranslatorBackend()

    objective_rows = []
    rating_rows = []
    clip_id = 0

    for lang in langs:
        for sent_idx, sentence in enumerate(SENTENCES):
            # Translate once per (lang, sentence); reuse for every backend so all
            # backends speak the EXACT same text — a fair comparison.
            if lang.lower() == "en":
                text = sentence
            else:
                try:
                    text = translator.translate(sentence, lang)
                except Exception as e:
                    print(f"  ! translation failed ({lang}): {e} — using English")
                    text = sentence

            for backend in backends:
                clip_id += 1
                engine = TTSFactory.get_backend(backend, lang)
                engine_name = engine.__class__.__name__

                t0 = time.perf_counter()
                try:
                    audio_bytes = engine.synthesize(text, lang=lang)
                except Exception as e:
                    print(f"  ! synth failed [{backend}/{lang}]: {e}")
                    continue
                synth_time = time.perf_counter() - t0

                if not audio_bytes:
                    print(f"  ! empty audio [{backend}/{lang}]")
                    continue

                duration = len(AudioSegment.from_file(io.BytesIO(audio_bytes))) / 1000.0
                rtf = synth_time / duration if duration > 0 else 0.0

                fname = f"clip{clip_id:02d}_{backend}_{lang}_s{sent_idx}.mp3"
                fpath = os.path.join(CLIP_DIR, fname)
                with open(fpath, "wb") as f:
                    f.write(audio_bytes)

                print(f"  [{clip_id:02d}] {backend:5s} {lang}  "
                      f"{synth_time:5.2f}s  dur={duration:4.1f}s  RTF={rtf:.3f}  -> {fname}")

                objective_rows.append({
                    "clip_id": clip_id, "backend": backend, "engine": engine_name,
                    "lang": lang, "sentence_idx": sent_idx, "file": fname,
                    "synth_time_s": round(synth_time, 3),
                    "duration_s": round(duration, 3),
                    "rtf": round(rtf, 4),
                    "bytes": len(audio_bytes),
                })
                rating_rows.append({
                    "clip_id": clip_id, "file": fname, "backend": backend, "lang": lang,
                    "naturalness_1to5": "", "intelligibility_1to5": "", "notes": "",
                })

    if not objective_rows:
        print("\nNo clips were generated — check your internet / backend names.")
        return

    with open(OBJECTIVE_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(objective_rows[0].keys()))
        w.writeheader()
        w.writerows(objective_rows)

    with open(RATING_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rating_rows[0].keys()))
        w.writeheader()
        w.writerows(rating_rows)

    print(f"\nGenerated {len(objective_rows)} clips in  {CLIP_DIR}")
    print(f"Objective stats written to        {OBJECTIVE_CSV}")
    print(f"\nNEXT STEP:")
    print(f"  1. Open the clips folder and LISTEN to each .mp3")
    print(f"  2. Open {RATING_CSV} and fill in, for each clip:")
    print(f"       naturalness_1to5     (5 = sounds human, 1 = robotic)")
    print(f"       intelligibility_1to5 (5 = perfectly clear, 1 = hard to understand)")
    print(f"  3. Run:  python scripts/tts_eval.py score")


# ---------------------------------------------------------------------------
# score
# ---------------------------------------------------------------------------
def _read_ratings():
    if not os.path.exists(RATING_CSV):
        print(f"No rating sheet found at {RATING_CSV}. Run 'generate' first.")
        return None
    rows = []
    with open(RATING_CSV, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            nat, intel = r.get("naturalness_1to5", ""), r.get("intelligibility_1to5", "")
            if not nat.strip() or not intel.strip():
                continue  # not yet rated
            try:
                r["_nat"] = float(nat)
                r["_intel"] = float(intel)
            except ValueError:
                continue
            rows.append(r)
    return rows


def _read_rtf():
    rtf = {}
    if os.path.exists(OBJECTIVE_CSV):
        with open(OBJECTIVE_CSV, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                rtf[r["clip_id"]] = float(r["rtf"])
    return rtf


def _avg(values):
    return sum(values) / len(values) if values else 0.0


def score():
    rows = _read_ratings()
    if rows is None:
        return
    if not rows:
        print(f"No completed ratings in {RATING_CSV}. Fill the 1-5 columns first.")
        return

    rtf = _read_rtf()

    by_backend = defaultdict(lambda: {"nat": [], "intel": [], "rtf": []})
    by_lang = defaultdict(lambda: {"nat": [], "intel": []})
    for r in rows:
        by_backend[r["backend"]]["nat"].append(r["_nat"])
        by_backend[r["backend"]]["intel"].append(r["_intel"])
        if r["clip_id"] in rtf:
            by_backend[r["backend"]]["rtf"].append(rtf[r["clip_id"]])
        by_lang[r["lang"]]["nat"].append(r["_nat"])
        by_lang[r["lang"]]["intel"].append(r["_intel"])

    print(f"\nRated clips: {len(rows)}\n")
    print("MOS BY BACKEND  (naturalness & intelligibility are 1-5, higher better)")
    print(f"{'backend':8s} {'MOS-nat':>8s} {'MOS-intel':>10s} {'avg-RTF':>9s} {'n':>4s}")
    print("-" * 43)
    for b, d in sorted(by_backend.items()):
        print(f"{b:8s} {_avg(d['nat']):8.2f} {_avg(d['intel']):10.2f} "
              f"{_avg(d['rtf']):9.3f} {len(d['nat']):4d}")

    print("\nMOS BY LANGUAGE")
    print(f"{'lang':8s} {'MOS-nat':>8s} {'MOS-intel':>10s} {'n':>4s}")
    print("-" * 33)
    for lng, d in sorted(by_lang.items()):
        print(f"{lng:8s} {_avg(d['nat']):8.2f} {_avg(d['intel']):10.2f} {len(d['nat']):4d}")

    print("\nReading: MOS-nat is the headline TTS-quality number. RTF < 1.0 means "
          "faster-than-real-time synthesis (good on CPU).")


# ---------------------------------------------------------------------------
# flores : speed + reliability benchmark over the real FLORES sentence set
# ---------------------------------------------------------------------------
FLORES_FILE = "flores_evaluation_set.json"
FLORES_CSV = os.path.join(OUT_DIR, "tts_flores_benchmark.csv")


def flores(langs, backends, sample):
    """Synthesize real FLORES sentences (already in the target language) and
    measure RTF + success rate. No translation, no human rating — pure,
    automatic, scalable performance measurement over standard data."""
    if not os.path.exists(FLORES_FILE):
        print(f"ERROR: '{FLORES_FILE}' not found in {os.getcwd()}.")
        print("Drop the FLORES json (the one from Colab) here. We only use its text.")
        return

    with open(FLORES_FILE, encoding="utf-8") as f:
        data = json.load(f)
    rows = data[:sample]
    print(f"Loaded {len(rows)} FLORES sentences. langs={langs} backends={backends}\n")

    os.makedirs(OUT_DIR, exist_ok=True)
    summary = []

    for lang in langs:
        if lang not in rows[0]:
            print(f"{lang}: no sentences in file — skipped")
            continue
        sentences = [r[lang].strip().strip('"').strip() for r in rows if r.get(lang)]

        for backend in backends:
            engine = TTSFactory.get_backend(backend, lang)
            ok, fail = 0, 0
            synth_time_total, audio_dur_total = 0.0, 0.0
            t_start = time.perf_counter()

            for i, text in enumerate(sentences):
                if not text:
                    continue
                try:
                    t0 = time.perf_counter()
                    audio = engine.synthesize(text, lang=lang)
                    dt = time.perf_counter() - t0
                    if not audio:
                        fail += 1
                        continue
                    dur = len(AudioSegment.from_file(io.BytesIO(audio))) / 1000.0
                    synth_time_total += dt
                    audio_dur_total += dur
                    ok += 1
                except Exception:
                    fail += 1
                if (i + 1) % 25 == 0:
                    print(f"  {backend}/{lang}: {i+1}/{len(sentences)} done...")

            wall = time.perf_counter() - t_start
            avg_rtf = (synth_time_total / audio_dur_total) if audio_dur_total > 0 else 0.0
            success = ok / (ok + fail) * 100 if (ok + fail) else 0.0
            print(f"[{backend}/{lang}] ok={ok} fail={fail} "
                  f"success={success:.1f}%  avg_RTF={avg_rtf:.3f}  wall={wall:.0f}s")
            summary.append({
                "backend": backend, "lang": lang, "sentences": ok + fail,
                "ok": ok, "fail": fail, "success_pct": round(success, 1),
                "avg_rtf": round(avg_rtf, 4),
                "total_audio_s": round(audio_dur_total, 1),
                "wall_s": round(wall, 1),
            })

    if not summary:
        print("\nNothing benchmarked — check the file's language keys.")
        return
    with open(FLORES_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(summary[0].keys()))
        w.writeheader()
        w.writerows(summary)
    print(f"\nSummary written to {FLORES_CSV}")
    print("Reading: avg_RTF < 1.0 = faster than real-time. success_pct = reliability.")


# ---------------------------------------------------------------------------
def main():
    p = argparse.ArgumentParser(description="Local CPU-only TTS (MOS) evaluation.")
    sub = p.add_subparsers(dest="mode", required=True)

    g = sub.add_parser("generate", help="make clips + objective stats + blank rating sheet")
    g.add_argument("--langs", nargs="+", default=DEFAULT_LANGS)
    g.add_argument("--backends", nargs="+", default=DEFAULT_BACKENDS)

    sub.add_parser("score", help="average the filled-in 1-5 ratings into MOS")

    fl = sub.add_parser("flores", help="speed+reliability benchmark over FLORES sentences")
    fl.add_argument("--langs", nargs="+", default=DEFAULT_LANGS)
    fl.add_argument("--backends", nargs="+", default=["gtts"])
    fl.add_argument("--sample", type=int, default=100,
                    help="How many FLORES sentences (max ~1012). Start small!")

    args = p.parse_args()
    if args.mode == "generate":
        print(f"Generating clips: langs={args.langs} backends={args.backends}\n")
        generate(args.langs, args.backends)
    elif args.mode == "score":
        score()
    elif args.mode == "flores":
        flores(args.langs, args.backends, args.sample)


if __name__ == "__main__":
    main()
