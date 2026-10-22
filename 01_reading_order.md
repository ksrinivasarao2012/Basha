# 📚 Basha — Reading Order Guide
> Read files in this exact order. Each file has ONE key thing to understand.
> Total time: ~2 hours

---

## 🟢 PHASE 1 — Understand What the Project IS
> Read these FIRST. No code yet. Just understand the "what".

---

### 1. `config/config.yaml`
📍 [`d:\Basha\config\config.yaml`](file:///d:/Basha/config/config.yaml)

```yaml
default_backend: gtts
translation_backend: deep_translator
cache:
  enabled: true
  max_size_mb: 512
chunking:
  max_chars: 240
```

**🔑 KEY THING:** This file controls the ENTIRE behavior of the app without touching Python code.
- `default_backend: gtts` → which TTS engine runs
- `max_chars: 240` → how long each text chunk is
- No code change needed to switch engines — just change this file.

---

### 2. `config/backends.yaml`
📍 [`d:\Basha\config\backends.yaml`](file:///d:/Basha/config/backends.yaml)

**🔑 KEY THING:** Lists ALL supported engines (gTTS, Edge-TTS, Indic Parler, XTTS, IndicTrans2, NLLB) and their model IDs. Shows the project is designed to be **upgradeable** — start free, upgrade to GPU models later.

---

### 3. `requirements.txt`
📍 [`d:\Basha\requirements.txt`](file:///d:/Basha/requirements.txt)

**🔑 KEY THING:** Look at the **two-tier structure**:
- **Tier 1** (install now): `fastapi`, `gtts`, `edge-tts`, `deep-translator`, `pydub` — works on any laptop, no GPU
- **Tier 2** (later): `torch`, `transformers`, GPU models — commented out

This shows thoughtful dependency design — the app is usable without heavy ML deps.

---

### 4. `Dockerfile`
📍 [`d:\Basha\Dockerfile`](file:///d:/Basha/Dockerfile)

```dockerfile
COPY requirements.txt .
RUN pip install -r requirements.txt   ← layer cached
COPY . .                              ← code copied after deps
CMD uvicorn basha.main:app --app-dir src --host 0.0.0.0 --port $PORT
```

**🔑 KEY THING:** `requirements.txt` is copied and installed BEFORE the source code. This is intentional — Docker caches layers. If only code changes (not deps), the `pip install` layer is reused → fast builds.

---

### 5. `src/basha/main.py`
📍 [`d:\Basha\src\basha\main.py`](file:///d:/Basha/src/basha/main.py)

```python
setup_logging()                        # 1. JSON logging
app = FastAPI(title="Basha API", ...)  # 2. Create app
app.add_middleware(RequestLoggingMiddleware)  # 3. Request tracing
app.include_router(api_router)         # 4. All endpoints
@app.get("/") def serve_ui(): ...      # 5. Serve frontend
```

**🔑 KEY THING:** Only 29 lines. Understand the startup sequence — logging → app → middleware → routes → UI. This IS the entire boot process.

---

## 🔵 PHASE 2 — Core Infrastructure
> The "engine room" — these 3 files power everything else.

---

### 6. `src/basha/core/config.py`
📍 [`d:\Basha\src\basha\core\config.py`](file:///d:/Basha/src/basha/core/config.py)

```python
class Settings:
    def __init__(self):
        # 1. Load config.yaml
        # 2. Load backends.yaml
        # 3. Read env vars (secrets)

settings = Settings()  # ← SINGLETON at module level
```

**🔑 KEY THING:** `settings = Settings()` at the bottom creates ONE global instance. Any file that does `from basha.core.config import settings` gets the SAME object. This is the **Singleton pattern**. Config is loaded once at startup, not on every request.

---

### 7. `src/basha/core/cache.py`
📍 [`d:\Basha\src\basha\core\cache.py`](file:///d:/Basha/src/basha/core/cache.py)

```python
def _get_key(self, text, lang, voice, backend):
    combined = f"{text.strip()}:{lang}:{voice}:{backend}"
    return hashlib.sha256(combined.encode()).hexdigest()
    # → "a3f9d2..." → saved as "audio_cache/a3f9d2....mp3"
```

**🔑 KEY THING:** The cache key is a **SHA256 hash** of (text + language + voice + backend). Same input → always same hash → same filename. This is called **content-addressed storage** (how Git works too). The file either exists (cache hit) or doesn't (cache miss) — no lookup table needed.

---

### 8. `src/basha/core/logging.py`
📍 [`d:\Basha\src\basha\core\logging.py`](file:///d:/Basha/src/basha/core/logging.py)

**🔑 KEY THING — THREE concepts in one file:**

**A. `JSONFormatter`** → logs as `{"timestamp":"..","level":"INFO","message":"..","request_id":"abc"}` — machine parseable

**B. `LogContext`** → context manager that auto-times code blocks:
```python
with LogContext("basha.pipeline", "translate_chunk_0"):
    translated = translator.translate(chunk, lang)
# Auto-logs: "Completed: translate_chunk_0 (after 0.234s)"
```

**C. `ContextVar`** → stores the `request_id` per async task (NOT a global variable):
```python
REQUEST_ID_VAR: ContextVar[str] = ContextVar("request_id", default="")
```
Every log message from that request automatically includes its ID. This is how you trace one request through hundreds of log lines.

---

## 🟡 PHASE 3 — The Contracts (Interfaces)
> These are the "rules" all implementations must follow.

---

### 9. `src/basha/translation/base.py`
📍 [`d:\Basha\src\basha\translation\base.py`](file:///d:/Basha/src/basha/translation/base.py)

```python
class TranslateBackend(ABC):
    @abstractmethod
    def translate(self, text: str, target_lang: str) -> str: ...
```

**🔑 KEY THING:** 17 lines. This is an **Abstract Base Class** — a contract. Any translation engine (Google, DeepL, IndicTrans2) MUST implement `.translate()`. The pipeline only talks to this interface, not the concrete class.

---

### 10. `src/basha/tts/base.py`
📍 [`d:\Basha\src\basha\tts\base.py`](file:///d:/Basha/src/basha/tts/base.py)

```python
class TTSBackend(ABC):
    @abstractmethod
    def synthesize(self, text: str, lang: str, voice: str = None) -> bytes: ...
```

**🔑 KEY THING:** 18 lines. Same idea as translation. All TTS engines return `bytes` (raw audio). The pipeline doesn't care if it's gTTS or Edge-TTS — it just calls `.synthesize()`.

---

### 11. `src/basha/api/schemas.py`
📍 [`d:\Basha\src\basha\api\schemas.py`](file:///d:/Basha/src/basha/api/schemas.py)

```python
class SynthesizeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)
    target_language: str = Field(default='hi')
    voice: Optional[str] = Field(None)
    backend: Optional[str] = Field("auto")

class JobStatusResponse(BaseModel):
    job_id: str
    status: str  # "pending" | "processing" | "completed" | "failed"
    metrics: Optional[JobMetrics] = None
```

**🔑 KEY THING:** Pydantic models = **automatic validation**. If a request sends `text=""` or exceeds 2000 chars, FastAPI auto-returns a 422 error. You write ZERO manual validation code. The schema IS the documentation (visible in `/docs`).

---

## 🟠 PHASE 4 — Concrete Implementations
> Now you see HOW the contracts are actually fulfilled.

---

### 12. `src/basha/translation/deep_translator_backend.py`
📍 [`d:\Basha\src\basha\translation\deep_translator_backend.py`](file:///d:/Basha/src/basha/translation/deep_translator_backend.py)

```python
def translate(self, text, target_lang):
    if target_lang.lower() == 'en':
        return text  # ← short-circuit!
    return GoogleTranslator(source='en', target=target_lang).translate(text)
```

**🔑 KEY THING:** The `if target_lang == 'en': return text` guard. Without it, calling this for an English-to-English scene would waste an API call. Small guard, big impact.

---

### 13. `src/basha/tts/gtts_backend.py`
📍 [`d:\Basha\src\basha\tts\gtts_backend.py`](file:///d:/Basha/src/basha/tts/gtts_backend.py)

```python
for attempt in range(3):
    try:
        tts = gTTS(text=text, lang=lang)
        fp = io.BytesIO()
        tts.write_to_fp(fp)   # ← in-memory, no temp file
        fp.seek(0)
        return fp.read()
    except Exception as e:
        if attempt == 2: raise e
        time.sleep(2.0 * (attempt + 1))  # backoff: 2s, 4s
```

**🔑 KEY THING:** Two things — `io.BytesIO()` (everything in-memory, no temp files on disk) + **retry with exponential backoff** (Google rate-limits free TTS). Pattern: try 3 times, wait 2s then 4s.

---

### 14. `src/basha/tts/edge_tts.py`
📍 [`d:\Basha\src\basha\tts\edge_tts.py`](file:///d:/Basha/src/basha/tts/edge_tts.py)

```python
async def _run():
    comm = Communicate(text, voice_id)
    buf = bytearray()
    async for chunk in comm.stream():
        if chunk["type"] == "audio":
            buf.extend(chunk["data"])   # ← streaming!
    return bytes(buf)

return asyncio.run(_run())  # ← sync wrapper around async
```

**🔑 KEY THING:** Edge-TTS **streams** audio chunks (not one big response). We collect them into a `bytearray` and return as `bytes`. Also: `asyncio.run()` bridges async → sync. This is required because the Edge-TTS library is async-only.

---

### 15. `src/basha/tts/factory.py`
📍 [`d:\Basha\src\basha\tts\factory.py`](file:///d:/Basha/src/basha/tts/factory.py)

```python
class TTSFactory:
    _backends = {
        "gtts": GTTSBackend,
        "edge": EdgeTTSBackend
    }

    @classmethod
    def get_backend(cls, name, lang=None):
        if name == "auto": return GTTSBackend()
        if name in cls._backends: return cls._backends[name]()
        return GTTSBackend()  # ← safe fallback
```

**🔑 KEY THING:** **Factory Pattern**. The `_backends` dict is a registry. To add a new engine: implement `TTSBackend`, add one line to `_backends`. Zero changes to the pipeline. The class method returns a new *instance* (not the class itself).

---

### 16. `src/basha/tts/voices.py`
📍 [`d:\Basha\src\basha\tts\voices.py`](file:///d:/Basha/src/basha/tts/voices.py)

```python
class VoiceManager:
    _voice_cache: Dict[str, List] = {}         # CLASS-level (shared)
    _round_robin_index: Dict[str, int] = {}    # CLASS-level (shared)

    def get_voice(self, speaker, target_lang, gender=None, exclude=None):
        # Priority 1: explicit map  {"Ravi": "hi-IN-MadhavNeural"}
        # Priority 2: gender pool   male voices → round-robin
        # Priority 3: any voice     round-robin from all available
```

**🔑 KEY THING:** `_voice_cache` and `_round_robin_index` are **class variables** — shared across ALL VoiceManager instances in the process. The voice list is fetched from Edge-TTS API ONCE per language and reused. Round-robin ensures no two characters get the same voice.

---

## 🔴 PHASE 5 — The Pipeline (The Heart of the System)
> This is where all the pieces connect.

---

### 17. `src/basha/pipeline/chunker.py`
📍 [`d:\Basha\src\basha\pipeline\chunker.py`](file:///d:/Basha/src/basha/pipeline/chunker.py)

```python
# Split AFTER punctuation (lookbehind keeps punctuation with the sentence)
sentences = re.split(r'(?<=[.?!;,])\s+', text)

# Then accumulate into chunks ≤ 240 chars
# If a sentence > 240: split by words
# If a word > 240: hard-split by characters
```

**🔑 KEY THING:** The **lookbehind regex** `(?<=[.?!;,])`. Without it, `"Hello. World"` splits as `["Hello.", " World"]` with a space. With lookbehind, it splits at the space AFTER punctuation, preserving the sentence structure. Also: three-level fallback (sentence → word → character) for edge cases.

---

### 18. `src/basha/pipeline/stitcher.py`
📍 [`d:\Basha\src\basha\pipeline\stitcher.py`](file:///d:/Basha/src/basha/pipeline/stitcher.py)

```python
_ffmpeg = shutil.which("ffmpeg")   # ← find on PATH, not hardcoded
if _ffmpeg:
    AudioSegment.converter = _ffmpeg

combined = AudioSegment.empty()
silence = AudioSegment.silent(duration=150)  # 150ms pause
for i, clip in enumerate(audio_clips):
    segment = AudioSegment.from_file(io.BytesIO(clip))
    combined = segment if i == 0 else combined + silence + segment

out = io.BytesIO()
combined.export(out, format="mp3")
return out.read()
```

**🔑 KEY THING:** `shutil.which("ffmpeg")` — finds ffmpeg on system PATH without hardcoding `/usr/bin/ffmpeg`. Works on Windows, macOS, Linux, Docker. Everything stays in-memory (`io.BytesIO`) — no temp files.

---

### 19. `src/basha/script/parser.py`
📍 [`d:\Basha\src\basha\script\parser.py`](file:///d:/Basha/src/basha/script/parser.py)

```python
parts = line.split(":", 1)   # maxsplit=1 ← CRITICAL
# "Ravi: It's 5:30 PM" → ["Ravi", "It's 5:30 PM"] ✓
# Without maxsplit=1:  → ["Ravi", "It's 5", "30 PM"] ✗
```

**🔑 KEY THING:** `split(":", 1)` — the `1` limits to ONE split. Without it, dialogue like `"Ravi: Time is 5:30"` would break incorrectly. Lines without a colon → `speaker = None` → treated as narration.

---

### 20. `src/basha/script/gender.py`
📍 [`d:\Basha\src\basha\script\gender.py`](file:///d:/Basha/src/basha/script/gender.py)

```python
_MALE = {"ravi", "arjun", "john", ...}   # curated set
_FEMALE = {"meena", "priya", "emma", ...}  # curated set

def guess_gender(name):
    key = name.strip().split()[0].lower()   # "Ravi Kumar" → "ravi"
    if key in _MALE: return "male"
    if key in _FEMALE: return "female"
    if _detector:  # gender-guesser package if installed
        ...
    return None   # unknown → caller does round-robin
```

**🔑 KEY THING:** The function returns `None` for unknown names — it **never guesses wrong**. Unisex names like "Kiran" are intentionally NOT in either set. A `None` result triggers round-robin assignment, which is always better than assigning the wrong gender voice.

---

### 21. `src/basha/pipeline/orchestrator.py` ⭐ MOST IMPORTANT FILE
📍 [`d:\Basha\src\basha\pipeline\orchestrator.py`](file:///d:/Basha/src/basha/pipeline/orchestrator.py)

**Read this file last in the phase. Understand the full flow:**

**`process()` — single-voice pipeline:**
```
text
  ↓ split_text_into_chunks()           → [chunk1, chunk2, ...]
  ↓ for each chunk:
       translator.translate(chunk)     → translated text
       cache.get(translated, ...)      → HIT: use it / MISS: synthesize
       tts_backend.synthesize(...)     → audio bytes
       cache.set(...)                  → save for next time
  ↓ stitch_audio_chunks(all_clips)    → final MP3 bytes
  ↓ compute metrics (RTF, cache%)
  ↓ return (audio_bytes, metrics)
```

**`process_scene()` — multi-voice drama pipeline:**
```
script
  ↓ parse_dialogue()                  → [(speaker, utterance), ...]
  ↓ VoiceManager() setup
  ↓ reserve narrator_voice (fixed male voice)
  ↓ for each (speaker, utterance):
       split_gender_tag()             → (clean_name, gender_hint)
       vm.get_voice(speaker, ...)     → voice_id (once per speaker)
       translator.translate(line)     → translated utterance
       if speaker changed: synthesize "Ravi is speaking."
       cache.get / tts.synthesize     → clip bytes
  ↓ stitch_audio_chunks(all, pause_ms=300)
  ↓ return (audio, cast_dict, transcript, metrics)
```

**🔑 KEY THING:** The orchestrator is the **only class that knows about ALL other modules**. Everything else is isolated. This is the **Façade pattern** — one entry point hides all complexity.

---

## 🟣 PHASE 6 — API Surface

---

### 22. `src/basha/jobs/queue.py`
📍 [`d:\Basha\src\basha\jobs\queue.py`](file:///d:/Basha/src/basha/jobs/queue.py)

```python
class JobQueueManager:
    def __init__(self):
        self._jobs: Dict[str, Dict] = {}
        self._lock = threading.Lock()   # ← thread safety

    # State machine:
    # create_job()   → status: "pending"
    # start_job()    → status: "processing"
    # complete_job() → status: "completed" + result_key + metrics
    # fail_job()     → status: "failed" + error
```

**🔑 KEY THING:** `threading.Lock()` — FastAPI's `BackgroundTasks` run in a **thread pool** (not the async event loop). Multiple jobs can run in parallel threads. The lock prevents two threads from writing to `_jobs` dict simultaneously. Without it → race conditions → corrupted state.

---

### 23. `src/basha/api/routes.py` ⭐ SECOND MOST IMPORTANT
📍 [`d:\Basha\src\basha\api\routes.py`](file:///d:/Basha/src/basha/api/routes.py)

**Endpoints to understand:**

| Endpoint | Critical Detail |
|----------|----------------|
| `POST /synthesize` | Synchronous — waits for audio, returns `audio/mpeg` directly |
| `POST /scene` | Returns audio + `X-Cast`, `X-Script` (base64!), `X-Metrics` headers |
| `POST /jobs` | Returns **202 Accepted** immediately, runs pipeline in background |
| `GET /jobs/{id}` | Poll for status |
| `GET /jobs/{id}/download` | Download completed MP3 |
| `GET /health` | Tests internet via `socket.connect("1.1.1.1", 53)` |

**🔑 KEY THING — `/scene` header encoding:**
```python
# Non-ASCII (Telugu/Hindi) can't go in HTTP headers raw
script_b64 = base64.b64encode(
    json.dumps(transcript, ensure_ascii=False).encode("utf-8")
).decode("ascii")
headers = {"X-Script": script_b64}
```
HTTP headers only support ASCII. Telugu/Hindi characters are Unicode. Solution: JSON → UTF-8 bytes → base64 encode → ASCII string that headers can carry.

---

## ⚫ PHASE 7 — Quality & Evaluation

---

### 24. `src/basha/eval/metrics.py`
📍 [`d:\Basha\src\basha\eval\metrics.py`](file:///d:/Basha/src/basha/eval/metrics.py)

```python
# CER = Character Error Rate
distance = _levenshtein_distance(ref, hyp)   # char by char
return distance / len(ref)

# WER = Word Error Rate
distance = _levenshtein_distance(ref.split(), hyp.split())  # word by word
return distance / len(ref_words)

# RTF = Real-Time Factor
return synthesis_time / audio_duration   # < 1.0 = faster than real-time

# Semantic Similarity = cosine similarity of BERT embeddings
emb1 = model.encode(reference)
emb2 = model.encode(hypothesis)
return cos_sim(emb1, emb2)
```

**🔑 KEY THING:** `normalize_text()` is called BEFORE any metric. It strips punctuation, lowercases, NFC-normalizes unicode. Without it, "Hello!" vs "Hello" would show as different. For Indic scripts it preserves **combining vowel signs** (Unicode category `M`) — removing them would destroy the meaning.

---

### 25. `src/basha/eval/asr_roundtrip.py`
📍 [`d:\Basha\src\basha\eval\asr_roundtrip.py`](file:///d:/Basha/src/basha/eval/asr_roundtrip.py)

```
Synthesized audio (MP3)
  → pydub: convert to WAV (Google ASR requires WAV)
  → speech_recognition: send to Google STT
  → get back text
  → compare to original → compute CER/WER
```

**🔑 KEY THING:** This is a **closed-loop evaluation** — synthesize speech, then transcribe it back to text, then measure accuracy. It answers: "Did the TTS actually speak the right words?" This runs OFFLINE (not on live requests) — too slow and rate-limited for production use.

---

### 26. `tests/test_api.py`
📍 [`d:\Basha\tests\test_api.py`](file:///d:/Basha/tests/test_api.py)

```python
@patch("basha.api.routes.orchestrator.process")
def test_synthesize_returns_audio(mock_process):
    mock_process.return_value = (b"FAKE_MP3_BYTES", {"rtf": 0.2})
    resp = client.post("/synthesize", json={"text": "Hello", "target_language": "de"})
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "audio/mpeg"
```

**🔑 KEY THING:** The pipeline is **mocked** at the orchestrator level. Tests run offline, instantly, deterministically. They verify HTTP behavior (status codes, headers, content-type) — NOT audio quality. This is the correct separation: unit test the HTTP layer, integration test the pipeline separately.

---

## 📊 Quick Reference — File Size vs Importance

| File | Lines | Importance | Why |
|------|-------|-----------|-----|
| `orchestrator.py` | 281 | ⭐⭐⭐⭐⭐ | Ties everything together |
| `routes.py` | 272 | ⭐⭐⭐⭐⭐ | The public API surface |
| `voices.py` | 175 | ⭐⭐⭐⭐ | Most complex class |
| `logging.py` | 147 | ⭐⭐⭐⭐ | 3 key patterns in 1 file |
| `metrics.py` | 108 | ⭐⭐⭐ | DSA + NLP evaluation |
| `gender.py` | 115 | ⭐⭐⭐ | Heuristic AI |
| `schemas.py` | 84 | ⭐⭐⭐ | API contract |
| `chunker.py` | 77 | ⭐⭐⭐⭐ | Algo interview worthy |
| `queue.py` | 72 | ⭐⭐⭐⭐ | Thread safety |
| `config.py` | 54 | ⭐⭐⭐ | Singleton + layered config |
| `cache.py` | 54 | ⭐⭐⭐⭐ | Content-addressed storage |
| `asr_roundtrip.py` | 54 | ⭐⭐ | Evaluation only |
| `edge_tts.py` | 48 | ⭐⭐⭐ | Async bridging |
| `stitcher.py` | 49 | ⭐⭐⭐ | Audio processing |
| `factory.py` | 36 | ⭐⭐⭐ | Factory pattern |
| `parser.py` | 34 | ⭐⭐ | Simple but tricky |
| `gtts_backend.py` | 28 | ⭐⭐ | Retry pattern |
| `main.py` | 29 | ⭐⭐ | Entry point |
| `tts/base.py` | 18 | ⭐⭐ | ABC contract |
| `translation/base.py` | 17 | ⭐⭐ | ABC contract |
| `deep_translator_backend.py` | 19 | ⭐⭐ | Simple impl |
