# PITFALLS & DESIGN DECISIONS — read before writing each file

These are the real failure modes for **Basha** on a CPU-only Windows laptop, and the
exact decision we take for each. When you build a file, check this list first.

---

## 1. Cache key MUST be deterministic — never use `hash()`  [file: `src/basha/core/cache.py`]

**Trap:** Python's built-in `hash()` on strings/bytes is randomized per process
(`PYTHONHASHSEED`). Restart the server → every key changes → 100% cache misses + orphaned
files.

**Decision:** key the cache with **SHA-256** from `hashlib`.

```python
import hashlib

def get_cache_key(text: str, lang: str, voice: str = "default") -> str:
    raw = f"{text}:{lang}:{voice}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
```

The hex digest is also a safe filename, so cached audio = `cache/<key>.mp3`.

---

## 2. The /synthesize route MUST be sync `def`, not `async def`  [file: `src/basha/api/routes.py`]

**Trap:** `gtts`, `deep-translator`, `pydub`, `requests` are **blocking**. Inside an
`async def` route they freeze FastAPI's single event loop — `/health` and every other
request hangs until synthesis finishes.

**Decision:** define blocking routes as plain `def`. FastAPI automatically runs them in a
threadpool, so concurrent requests still work.

```python
@router.post("/synthesize")
def synthesize(request: SynthesizeRequest):   # NOTE: def, not async def
    ...
```

(Only use `async def` for routes that are truly async all the way down — we have none.)

---

## 3. gTTS / deep-translator get rate-limited (HTTP 429)  [files: `pipeline/orchestrator.py`, `eval/benchmark.py`]

**Trap:** both hit Google's **unofficial** web endpoints. Translating/synthesizing many
sentences in a tight loop → Google temporarily blocks your IP (429 / CAPTCHA).

**Decision:**
- Put a small `time.sleep(0.5–1.0)` between requests in any *batch* loop (benchmark, long
  multi-chunk jobs). A single short synthesis is fine.
- Catch the HTTP error and return a clean API error instead of a stack trace.
- **Interview line:** *"I wrapped these behind swappable interfaces because unofficial web
  scraping is rate-limited; in production you swap in Google Cloud TTS / Azure / Sarvam or
  a local model without touching the pipeline."*

---

## 4. Audio stitching + ffmpeg — AVOIDED on the MVP path  [files: `pipeline/stitcher.py`, `orchestrator.py`]

**Trap (the original concern):** `pydub` needs **ffmpeg** for MP3, and on Windows ffmpeg
often isn't on PATH until every terminal/editor is restarted → pydub crashes. Also, naively
joining waveforms causes audible **clicks**.

**Decision — sidestep both for the MVP:** with gTTS you do **not** stitch audio.
1. Chunk the text (needed because deep-translator caps ~5000 chars per call).
2. Translate each text chunk.
3. **Re-join the translated TEXT into one string.**
4. Make **one** gTTS call on the whole string → **one clean MP3**.

No pydub, no ffmpeg, no clicks. `stitcher.py` stays in the repo as a real feature for the
*per-chunk audio* path (multi-voice / local models) — documented, not on tonight's path.

**If you DO stitch audio later:**
- Keep clips as **WAV** and concatenate with the stdlib `wave` module or `soundfile`
  (no ffmpeg needed for WAV).
- Insert 100–200 ms of silence between clauses, or `pydub`'s `append(next, crossfade=50)`,
  to kill clicks and sound like natural breathing pauses.

---

## 5. The ASR evaluation gate is CPU-poison — keep it OPTIONAL  [files: `eval/asr_roundtrip.py`, `tests/test_eval.py`]

**Trap:** Whisper / IndicWhisper are large neural nets. Transcribing on CPU is minutes per
clip → your test suite hangs.

**Decision:** the eval gate is a **stretch goal, not in the MVP.** If you attempt it:
- Use the smallest model (`tiny` / `base`) via **`faster-whisper`** (optimized C++/CTranslate2,
  far quicker on CPU than the HuggingFace pipeline).
- Mark these tests `@pytest.mark.slow` / skip-by-default so `pytest` stays fast and green.
- Run the benchmark **manually**, once, not in CI.

---

## Summary: what these decisions change in the build order

- `core/cache.py` → SHA-256 keys (pitfall 1).
- `api/routes.py` → sync `def` routes (pitfall 2).
- `pipeline/orchestrator.py` → translate-then-join-text-then-one-gTTS-call; add `sleep`
  in batch loops (pitfalls 3 & 4).
- `pipeline/stitcher.py` → keep, but it's off the MVP critical path (pitfall 4).
- `eval/*` and `tests/test_eval.py` → optional, skipped by default (pitfall 5).
