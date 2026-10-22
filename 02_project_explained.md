# 🗺️ Basha — Complete Project Explanation (Step by Step)

> This document explains the **entire Basha project from scratch** — what it is, why it was built
> this way, and exactly how every file connects to every other. Read it top to bottom once and you
> will understand the full system.
>
> **Improved over `01_reading_order.md`:** The original reading order groups files by "phase" but
> jumps between low-level detail and high-level concepts. This document follows the **mental model**
> order — we first understand the *problem*, then the *solution shape*, then each layer from
> outside-in (API → Pipeline → Engines → Infrastructure).

---

## 🧠 STEP 0 — What Problem Does Basha Solve?

**The problem in one sentence:**
> Given an English text, translate it into a target language and produce natural-sounding narrated
> audio — reliably, without a GPU, for free.

### The Challenge

- Translation APIs exist, TTS engines exist — but they all have limits.
- Long text cannot be sent to a TTS engine in one shot (engines have character limits, network
  timeouts, and rate limits).
- Some languages need special engines. Indian languages (Telugu, Tamil, Hindi) have different TTS
  characteristics from European languages (German, French, Spanish).
- Re-synthesizing the same text every time is wasteful — both slow and API-rate-limited.
- A drama/podcast needs **multiple distinct voices** per character, not a single monotone voice.

### The Solution — Basha

Basha wraps all of that complexity behind a clean HTTP API:

```
User sends: English text  +  target language  +  optional voice/backend
Basha does:
  1. Split text into safe-size chunks
  2. Translate each chunk (free, via Google Translate)
  3. Check cache — already synthesized? Serve instantly
  4. If not cached: synthesize with gTTS / Edge-TTS
  5. Stitch all audio chunks into one seamless MP3
  6. Return MP3 + performance metrics
```

---

## 📁 STEP 1 — What the Project Looks Like (Directory Map)

```
d:\Basha\
├── config/                  ← Runtime configuration (YAML files, no code)
│   ├── config.yaml          ← Which TTS/translation engine? Cache settings?
│   └── backends.yaml        ← Model IDs and parameters per engine
│
├── src/basha/               ← All Python source code
│   ├── main.py              ← App entry point (FastAPI startup)
│   ├── api/
│   │   ├── routes.py        ← HTTP endpoints (/synthesize, /scene, /jobs, /health)
│   │   └── schemas.py       ← Pydantic request/response models (validation)
│   ├── core/
│   │   ├── config.py        ← Loads config.yaml + env vars into a Settings singleton
│   │   ├── cache.py         ← SHA-256 keyed audio cache (disk-based)
│   │   └── logging.py       ← JSON-structured logging with request-ID tracing
│   ├── tts/
│   │   ├── base.py          ← TTSBackend Abstract Base Class (the contract)
│   │   ├── gtts_backend.py  ← gTTS implementation (free, CPU, retry logic)
│   │   ├── edge_tts.py      ← Edge-TTS implementation (neural, gendered voices)
│   │   ├── voices.py        ← VoiceManager (assigns distinct voices to characters)
│   │   └── factory.py       ← TTSFactory (resolves which backend to use)
│   ├── translation/
│   │   ├── base.py          ← TranslateBackend Abstract Base Class
│   │   └── deep_translator_backend.py ← Google Translate wrapper implementation
│   ├── pipeline/
│   │   ├── chunker.py       ← Splits long text into ≤240-char chunks
│   │   ├── stitcher.py      ← Joins audio clips into one MP3
│   │   └── orchestrator.py  ← THE HEART — coordinates all the above
│   ├── script/
│   │   ├── parser.py        ← Parses "Speaker: dialogue" scripts
│   │   └── gender.py        ← Infers speaker gender from name (for voice assignment)
│   ├── jobs/
│   │   └── queue.py         ← Thread-safe in-memory job queue (pending/processing/done)
│   └── eval/
│       ├── metrics.py       ← CER, WER, RTF, semantic similarity calculations
│       └── asr_roundtrip.py ← Synthesize → transcribe back → compare (offline eval)
│
├── client/web/index.html    ← Web UI (served by the API itself)
├── tests/test_api.py        ← pytest tests for the HTTP layer (pipeline mocked)
├── Dockerfile               ← Container build (dependency caching trick)
├── requirements.txt         ← Two-tier: CPU-only (install now) + GPU (later)
└── 01_reading_order.md      ← Reference reading guide
```

---

## ⚙️ STEP 2 — Configuration Layer (The Control Panel)

> **No code change needed to switch engines.** All runtime behaviour is controlled by YAML files.

### 2a. `config/config.yaml` — The Master Switch

```yaml
default_backend: gtts          # Which TTS engine runs by default
translation_backend: deep_translator  # Which translator runs

cache:
  enabled: true
  max_size_mb: 512             # Never re-synthesize the same request

chunking:
  max_chars: 240               # Split long text at clause boundaries above this
```

**Why this matters:** If you want to switch from gTTS to Edge-TTS, you change
`default_backend: edge` here. Zero Python changes required.

### 2b. `config/backends.yaml` — Engine Registry

```yaml
tts:
  gtts:
    slow: false                # Standard speed for gTTS

  indic_parler:                # GPU-only, for Indian languages
    model_id: "ai4bharat/indic-parler-tts"
    default_voice: "Divya"
    languages: [te, ta, kn, ml, mr, hi]

  xtts:                        # GPU-only, for European languages
    model_id: "tts_models/multilingual/multi-dataset/xtts_v2"
    languages: [en, de, fr, es, it, pt]

translation:
  deep_translator:
    provider: "google"         # Free, no key needed

  indictrans2:                 # GPU model from AI4Bharat
    model_id: "ai4bharat/indictrans2-en-indic-1B"
```

**Design insight:** The project is designed to start free (gTTS + deep_translator) and scale up
to GPU models later — just by editing this YAML. The code is already written to support the
upgrade path.

### 2c. `requirements.txt` — Two-Tier Dependencies

```
# TIER 1 — Install now, works on any laptop, no GPU
fastapi, uvicorn        ← API server
gtts, edge-tts          ← TTS engines
deep-translator         ← Translation
pydub                   ← Audio processing

# TIER 2 — Commented out, install when you have GPU
# torch, transformers   ← Heavy ML models
# sentence-transformers ← BERT evaluation
```

**Why this is smart:** The app is *usable* without ML dependencies. A developer on a basic laptop
can run the full service. GPU models are opt-in.

---

## 🚀 STEP 3 — Application Startup (`main.py`)

```python
# src/basha/main.py  — only 30 lines

setup_logging()                              # 1. JSON logging (before anything else)
app = FastAPI(title="Basha API", ...)       # 2. Create the FastAPI application
app.add_middleware(RequestLoggingMiddleware) # 3. Every request gets a UUID trace ID
app.include_router(api_router)               # 4. Register all HTTP endpoints
@app.get("/")                               # 5. Root URL → serve the web UI HTML
def serve_ui():
    return FileResponse("client/web/index.html")
```

**Boot sequence — exactly in this order:**
1. Logging is set up first so any startup errors are captured in JSON format.
2. FastAPI app is created (no routes yet).
3. Middleware wraps every future request before any route handler runs.
4. All routes from `routes.py` are registered.
5. The root URL serves the web UI (no separate frontend server needed).

---

## 🏗️ STEP 4 — Core Infrastructure (The Engine Room)

These three files in `src/basha/core/` are utilities used by *everything else*.

### 4a. `core/config.py` — The Settings Singleton

```python
class Settings:
    def __init__(self):
        # Step 1: Start with hard-coded safe defaults
        self.default_backend = "gtts"
        self.cache_enabled = True
        self.chunking_max_chars = 240

        # Step 2: Override with values from config.yaml (if it exists)
        if config_path.exists():
            with open(config_path) as f:
                config = yaml.safe_load(f)
                self.default_backend = config.get("default_backend", self.default_backend)
                # ... etc

        # Step 3: Load all engine configs from backends.yaml
        self.backends = yaml.safe_load(backends_file)

        # Step 4: Override secrets from environment variables
        self.hf_token = os.getenv("HF_TOKEN", "")

settings = Settings()   # SINGLETON: created once at module import time
```

**The Singleton pattern:** `settings = Settings()` runs at module import time. Every file that
does `from basha.core.config import settings` gets the **exact same object** in memory. Config
is parsed once at startup, never on every request.

### 4b. `core/cache.py` — Content-Addressed Audio Cache

```python
class AudioCache:
    def _get_key(self, text, lang, voice, backend) -> str:
        # Combine all 4 dimensions into one string, then SHA-256 hash it
        combined = f"{text.strip()}:{lang.lower()}:{voice_str}:{backend_str}"
        return hashlib.sha256(combined.encode("utf-8")).hexdigest()
        # "Hello:hi:default:gttsbackend" → "a3f9d2c7e8b1..." (64-char hex)

    def get(self, text, lang, voice, backend) -> bytes | None:
        key = self._get_key(text, lang, voice, backend)
        path = f"audio_cache/{key}.mp3"
        return open(path, "rb").read() if os.path.exists(path) else None

    def set(self, text, lang, audio_bytes, voice, backend):
        key = self._get_key(text, lang, voice, backend)
        open(f"audio_cache/{key}.mp3", "wb").write(audio_bytes)

    def clear(self):
        # Deletes every file from the audio_cache/ folder
```

**How Content-Addressed Storage works:**
- Same text + language + voice + backend → always same SHA-256 hash → always same filename.
- "Does the file exist?" = cache hit. No database, no lookup table.
- This is how Git stores file content internally. Simple, reliable, collision-proof.

**Cache key components:**

| Component | Example | Why included |
|-----------|---------|-------------|
| `text` | `"hello world"` | Different text = different audio |
| `lang` | `"hi"` | Same text, different language = different audio |
| `voice` | `"hi-IN-MadhavNeural"` | Same text+lang, different voice = different audio |
| `backend` | `"GTTSBackend"` | gTTS and Edge-TTS produce different audio quality |

### 4c. `core/logging.py` — Three Patterns in One File

**Pattern A — JSONFormatter:** Logs in machine-readable JSON instead of plain text.
```json
{"timestamp": "2026-09-18T09:00:00", "level": "INFO", "message": "Cache hit",
 "request_id": "abc-123", "duration_seconds": 0.234}
```
Why JSON? Logs can be fed into Elasticsearch, Datadog, or CloudWatch for filtering.

**Pattern B — LogContext:** A context manager that auto-times code blocks.
```python
with LogContext("basha.pipeline", "translate_chunk_0"):
    translated = translator.translate(chunk, lang)
# Logs: "Completed: translate_chunk_0 (after 0.234s)"
# On error: "Failed: translate_chunk_0 (after 0.001s)" + full exception
```

**Pattern C — ContextVar for Request ID per-async-task isolation:**
```python
REQUEST_ID_VAR: ContextVar[str] = ContextVar("request_id", default="")
```
When request A and request B run concurrently, each gets its own `request_id` in the
ContextVar — they never contaminate each other. Every log line automatically includes
its request's ID so you can trace one user's request through hundreds of log lines.

---

## 📜 STEP 5 — The Contracts (Abstract Base Classes)

Before looking at any real TTS or translation code, understand the *interfaces* they must obey.

### 5a. `translation/base.py` — Translation Contract (17 lines)

```python
from abc import ABC, abstractmethod

class TranslateBackend(ABC):
    @abstractmethod
    def translate(self, text: str, target_lang: str) -> str:
        pass
```

Any class that calls itself a translation backend **must** implement `.translate(text, target_lang)`
returning a `str`. The pipeline only talks to this interface. Google Translate, DeepL, or
IndicTrans2 are all interchangeable — zero pipeline code changes needed.

### 5b. `tts/base.py` — TTS Contract (18 lines)

```python
from abc import ABC, abstractmethod

class TTSBackend(ABC):
    @abstractmethod
    def synthesize(self, text: str, lang: str, voice: str = None) -> bytes:
        pass
```

Any TTS engine must accept text and return `bytes` (raw audio). gTTS, Edge-TTS, Indic Parler,
XTTS — all implement this same method signature. The orchestrator never cares which one it is.

### 5c. `api/schemas.py` — API Validation Contracts

```python
class SynthesizeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)   # Required, validated
    target_language: str = Field(default='hi')              # Optional, defaults Hindi
    voice: Optional[str] = Field(None)
    backend: Optional[str] = Field("auto")

class JobSubmitRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=50000)  # Jobs: much larger text
    target_language: str = Field(default='hi')
    voice: Optional[str] = Field(None)
    gender: Optional[str] = Field(None)   # "male" or "female"
    backend: Optional[str] = Field("auto")

class SceneRequest(BaseModel):
    script: str = Field(..., min_length=1, max_length=20000)  # "Speaker: text" script
    target_language: str = Field(default="en")
    translate: bool = Field(default=True)
    voice_map: Optional[Dict[str, str]] = Field(None)  # {"Ravi": "hi-IN-MadhavNeural"}

class JobStatusResponse(BaseModel):
    job_id: str
    status: str      # "pending" | "processing" | "completed" | "failed"
    created_at: float
    completed_at: Optional[float] = None
    error: Optional[str] = None
    download_url: Optional[str] = None
    metrics: Optional[JobMetrics] = None
```

**Why Pydantic?** FastAPI + Pydantic gives you automatic validation with zero code:
- `text=""` → FastAPI automatically returns HTTP 422, no code written.
- `text` of 3000 chars → 422, automatically.
- Invalid JSON body → 422, automatically.
- The schema appears in `/docs` (Swagger UI) automatically.

---

## 🔧 STEP 6 — Concrete Implementations (Engines)

Now the contracts are fulfilled by real code.

### 6a. Translation — `translation/deep_translator_backend.py`

```python
class DeepTranslatorBackend(TranslateBackend):  # implements the ABC
    def translate(self, text: str, target_lang: str) -> str:
        if target_lang.lower() == 'en':
            return text   # SHORT-CIRCUIT: English→English = waste of API call

        return GoogleTranslator(source='en', target=target_lang).translate(text)
```

**The `if target_lang == 'en': return text` guard:** Without this, any English-mode scene or
request would still call Google's API for every line. This one check makes English-mode near-instant
and avoids hitting rate limits unnecessarily.

### 6b. gTTS Backend — `tts/gtts_backend.py`

```python
class GTTSBackend(TTSBackend):
    def synthesize(self, text: str, lang: str, voice: str = None) -> bytes:
        for attempt in range(3):          # Try up to 3 times
            try:
                tts = gTTS(text=text, lang=lang, slow=False)
                fp = io.BytesIO()         # In-memory buffer — no temp file on disk
                tts.write_to_fp(fp)
                fp.seek(0)
                return fp.read()
            except Exception as e:
                if attempt == 2:
                    raise e               # Give up after 3rd failure
                time.sleep(2.0 * (attempt + 1))  # Wait 2s, then 4s (backoff)
        return b''
```

**Two key patterns:**
1. **`io.BytesIO()` — in-memory:** Audio bytes are held in RAM, never written to disk as a
   temp file. Faster and cleaner (no cleanup code needed).
2. **Retry with exponential backoff:** Google's free TTS endpoint rate-limits. If call 1 fails,
   wait 2s and retry. If call 2 fails, wait 4s. On 3rd failure, raise the exception.

### 6c. Edge-TTS Backend — `tts/edge_tts.py`

```python
# When no voice is specified, pick a default neural voice for the language
_DEFAULT_VOICE = {
    "en": "en-US-AriaNeural",
    "hi": "hi-IN-SwaraNeural",
    "te": "te-IN-ShrutiNeural",
    # ...more languages...
}

class EdgeTTSBackend(TTSBackend):
    def synthesize(self, text: str, lang: str, voice: str = None) -> bytes:
        voice_id = voice or _DEFAULT_VOICE.get(lang.lower(), "en-US-AriaNeural")

        async def _run():
            comm = Communicate(text, voice_id)
            buf = bytearray()
            async for chunk in comm.stream():   # Audio arrives in streaming pieces
                if chunk["type"] == "audio":
                    buf.extend(chunk["data"])   # Accumulate all pieces
            return bytes(buf)

        return asyncio.run(_run())  # Bridge: run async library from sync context
```

**Two key patterns:**
1. **Streaming audio:** Edge-TTS doesn't return one big audio blob — it streams chunks. We
   collect them all into a `bytearray` and return as `bytes`. More memory-efficient.
2. **`asyncio.run()` bridge:** Edge-TTS library is async-only. Our `synthesize()` method is
   synchronous (part of the `TTSBackend` contract). `asyncio.run()` creates a temporary event
   loop, runs the async code to completion, and returns the result synchronously.

### 6d. TTS Factory — `tts/factory.py`

```python
class TTSFactory:
    _backends = {              # Registry: name string → backend class
        "gtts": GTTSBackend,
        "edge": EdgeTTSBackend,
    }

    @classmethod
    def get_backend(cls, name: str, lang: str = None) -> TTSBackend:
        name = (name or "auto").lower()
        if name == "auto":
            return GTTSBackend()           # Default: gTTS (free, CPU)
        if name in cls._backends:
            return cls._backends[name]()   # Instantiate the class, return instance
        return GTTSBackend()               # Unknown name → safe fallback
```

**Factory Pattern:** The `_backends` dict is a registry. To add a new TTS engine:
1. Create a class that implements `TTSBackend`.
2. Add one line to `_backends`: `"myengine": MyEngineBackend`.
3. Done — call with `backend="myengine"`, zero other code changes.

### 6e. Voice Manager — `tts/voices.py`

```python
class VoiceManager:
    _voice_cache: Dict[str, List] = {}        # CLASS variable: shared across all instances
    _round_robin_index: Dict[str, int] = {}   # CLASS variable: shared counter state

    def get_narrator_voice(self, target_lang: str) -> str:
        # Always returns the first male voice for the language (deterministic)
        # Same narrator voice every time = consistent-sounding narrator

    def get_voice(self, speaker, target_lang, gender=None, exclude=None) -> str:
        # Priority 1: explicit_map  (user forced "Ravi" → "hi-IN-MadhavNeural")
        # Priority 2: gender pool   (male/female voices, round-robin)
        # Priority 3: any voice     (round-robin from everything available)

    @staticmethod
    def validate_explicit_map(explicit_map, target_lang) -> dict:
        # Filters out any voice IDs that don't exist for the given language
        # Prevents silent failures from typos in voice IDs
```

**Key design choices:**
- `_voice_cache` is a **class variable** — the live Edge-TTS voice list is fetched **once per
  language** and reused across all instances. Without this, a 10-character scene would call the
  Edge-TTS API 10 times just to list available voices.
- **Round-robin** ensures different characters get different voices — no two characters in the
  same scene accidentally sound identical.
- **`exclude` list** keeps the Narrator's reserved voice out of the character pool.

---

## 🔬 STEP 7 — Script Utilities (for Audio Drama)

### 7a. `script/parser.py` — Dialogue Parser

```python
def parse_dialogue(script: str) -> List[Tuple[Optional[str], str]]:
    for line in script.splitlines():
        parts = line.split(":", 1)   # ← THE CRITICAL "1" — maxsplit=1

        # "Ravi: It's 5:30 PM" → ["Ravi", "It's 5:30 PM"]  ← CORRECT (maxsplit=1)
        # Without the 1:       → ["Ravi", "It's 5", "30 PM"] ← BROKEN

        if len(parts) == 2 and parts[0].strip():
            parsed.append((parts[0].strip(), parts[1].strip()))  # (speaker, dialogue)
        else:
            parsed.append((None, line))   # No colon → narration (speaker = None)
```

**Why `split(":", 1)`:** Limits the split to the FIRST colon only. Without `1`, any dialogue
with a colon (times like "5:30", colons in dialogue like "He said: wait") would be incorrectly
split into 3+ parts. A tiny detail with big correctness impact.

### 7b. `script/gender.py` — Gender Inference

```python
_MALE: Set[str] = {"ravi", "raj", "arjun", "john", "james", ...}  # curated list
_FEMALE: Set[str] = {"meena", "priya", "emma", "olivia", ...}      # curated list

def guess_gender(name: str) -> Optional[str]:
    key = name.strip().split()[0].lower()   # "Ravi Kumar" → "ravi"
    if key in _MALE:   return "male"
    if key in _FEMALE: return "female"
    if _detector:      # optional gender-guesser package if installed
        # check broader Western name database
    return None   # UNKNOWN → caller falls back to round-robin. Never guesses wrong.

def split_gender_tag(label: str) -> Tuple[Optional[str], Optional[str]]:
    # "Ravi (male)"     → ("Ravi", "male")
    # "Meena (f)"       → ("Meena", "female")
    # "Narrator"        → ("Narrator", None)
    # "Ravi (the king)" → ("Ravi (the king)", None)  ← non-gender tag preserved
```

**The `return None` design decision:** Ambiguous names (like "Kiran") return `None`. `None`
tells the orchestrator to use round-robin voice assignment. This is always better than
confidently assigning the wrong gender voice. **Safety over false confidence.**

---

## 🔀 STEP 8 — Pipeline Components (Chunker + Stitcher)

### 8a. `pipeline/chunker.py` — Text Splitting

```python
def split_text_into_chunks(text: str, max_chars: int = 240) -> List[str]:
    # Level 1: Split on clause boundaries (punctuation)
    sentences = re.split(r'(?<=[.?!;,])\s+', text)
    # "Hello. World!"   →  ["Hello.", "World!"]
    # (?<=...) is a "lookbehind" — matches whitespace AFTER punctuation

    # Level 2: If a sentence > 240 chars, split on word boundaries
    # Level 3: If a single word > 240 chars, split by characters (edge case: URLs)
```

**Three-level fallback logic:**
1. Split at sentence/clause boundaries → natural speech flow (preferred).
2. If one sentence > 240 chars, split on word boundaries → still readable.
3. If a single word > 240 chars (URL, identifier), split by characters → never crashes.

**Why the lookbehind regex `(?<=[.?!;,])`:**
- Without it: `"Hello. World"` → `["Hello.", " World"]` (leading space lost, causes issues)
- With lookbehind: splits only at the whitespace AFTER punctuation → `["Hello.", "World"]`

### 8b. `pipeline/stitcher.py` — Audio Assembly

```python
_ffmpeg = shutil.which("ffmpeg")   # Finds ffmpeg on system PATH, no hardcoded path
if _ffmpeg:
    AudioSegment.converter = _ffmpeg

def stitch_audio_chunks(audio_clips: List[bytes], pause_ms: int = 150) -> bytes:
    combined = AudioSegment.empty()
    silence = AudioSegment.silent(duration=pause_ms)   # 150ms gap between clips

    for i, clip_bytes in enumerate(audio_clips):
        segment = AudioSegment.from_file(io.BytesIO(clip_bytes))  # RAM only, no disk
        combined = segment if i == 0 else (combined + silence + segment)

    out_fp = io.BytesIO()
    combined.export(out_fp, format="mp3")
    out_fp.seek(0)
    return out_fp.read()
```

**`shutil.which("ffmpeg")` — portable binary discovery:** Instead of hardcoding `/usr/bin/ffmpeg`
(Linux-only) or `C:\ffmpeg\bin\ffmpeg.exe` (Windows-only), `shutil.which` searches the system
PATH. Works on Windows, macOS, Linux, and Docker containers identically.

**150ms pause between clips:** Natural breathing room between sentences. Without it, stitched
audio sounds rushed. For scene mode (speaker changes), 300ms — extra pause signals a different
person is now speaking.

---

## 🎭 STEP 9 — The Orchestrator (The Heart of the System)

**`src/basha/pipeline/orchestrator.py`** — 281 lines, the most important file.

The orchestrator is the only class that knows about *all* other modules. It's the Façade — one
entry point that hides all complexity from the API layer.

### 9a. Single-Voice Pipeline — `process()`

```
Input:  text (English),  target_lang,  backend,  voice,  gender
         ↓
Step 1: chunks = split_text_into_chunks(text)
         ↓
Step 2: Determine TTS backend
        - If gender specified but no voice → VoiceManager.get_voice(gender=gender)
        - If voice specified → force EdgeTTSBackend
        - Otherwise → TTSFactory.get_backend(backend_name)
         ↓
Step 3: For each chunk:
    a. translated = translator.translate(chunk, target_lang)
    b. cached = cache.get(translated, target_lang, voice, backend_name)
    c. If cached → append to audio_clips, count as HIT
    d. If not → clip = tts_backend.synthesize(translated, lang, voice)
               cache.set(translated, target_lang, clip, voice, backend_name)
               append to audio_clips
         ↓
Step 4: final_audio = stitch_audio_chunks(all_clips, pause_ms=150)
         ↓
Step 5: Compute metrics: translation_time, synthesis_time, cache_savings%, RTF
         ↓
Output: (final_audio_bytes, metrics_dict)
```

### 9b. Multi-Voice Drama Pipeline — `process_scene()`

```
Input:  script ("Ravi: Hello\nMeena: Hi"),  target_lang,  translate,  voice_map
         ↓
Step 1: lines = parse_dialogue(script) → [(speaker, utterance), ...]
         ↓
Step 2: VoiceManager setup:
        - Validate user's voice_map against live Edge-TTS voice list
        - vm = VoiceManager(valid_map)
         ↓
Step 3: Reserve narrator_voice (first male voice, deterministic/fixed)
         ↓
Step 4: For each (speaker, utterance):
    a. split_gender_tag(speaker) → (clean_name, gender_hint)
    b. Normalize: None/"narrator"/"NARRATOR" → always "Narrator"
    c. Assign voice per speaker (assigned ONCE, then remembered):
       - Narrator → narrator_voice (reserved, never assigned to characters)
       - Character → vm.get_voice(name, lang, gender)
    d. If translate=True and lang != "en":
       utterance = translator.translate(utterance, lang)
    e. If speaker changed → prepend announcement clip:
       "Ravi is speaking." (in Ravi's own voice)
    f. cache.get OR tts.synthesize(utterance, lang, voice_id) → clip
         ↓
Step 5: final_audio = stitch_audio_chunks(all_clips, pause_ms=300)
         ↓
Step 6: Compute metrics + cast dict + transcript list
         ↓
Output: (audio_bytes, cast_dict, transcript_list, metrics_dict)
```

**The "speaker announcement" trick:** When a speaker changes, a short announcement plays in
that speaker's own voice: `"Ravi is speaking."` This solves the problem of two characters
sharing a voice (common when a language has only one voice per gender) — the listener always
knows who is talking.

**The Façade Pattern:** The orchestrator imports from every other module. But `routes.py` (the
API layer) only imports from the orchestrator. The API layer is completely shielded from all
internal complexity.

---

## 🌐 STEP 10 — The Job Queue (Async Background Processing)

### `jobs/queue.py` — Thread-Safe State Machine

```python
class JobQueueManager:
    def __init__(self):
        self._jobs: Dict[str, Dict] = {}   # In-memory: job_id → job_data
        self._lock = threading.Lock()      # Thread safety for concurrent access

    # State machine transitions:
    def create_job(text, lang, voice)   → job_id    # status: "pending"
    def start_job(job_id)               → None      # status: "processing"
    def complete_job(job_id, key, metrics) → None   # status: "completed"
    def fail_job(job_id, error)         → None      # status: "failed"
    def get_job(job_id)                 → dict      # Read current state

job_manager = JobQueueManager()   # One shared singleton
```

**Why `threading.Lock()`?** FastAPI's `BackgroundTasks` run in a **thread pool** (not the async
event loop). When 3 users submit jobs simultaneously, 3 threads each call `complete_job()` at
the same time. Without the lock, threads corrupt each other's writes to `_jobs`. The lock ensures
only one thread touches `_jobs` at a time.

**Job lifecycle:**
```
POST /jobs     → create_job() → job_id returned immediately (HTTP 202 Accepted)
               ↓ [background thread starts]
             start_job()   → status: "processing"
               ↓ [pipeline runs: translate + synthesize + stitch]
             complete_job() → status: "completed", MP3 saved to disk
          OR fail_job()    → status: "failed", error recorded

GET /jobs/{id}             → returns current status + metrics
GET /jobs/{id}/download    → returns the MP3 file (only if "completed")
```

---

## 🔌 STEP 11 — The API Surface (`routes.py`)

All HTTP endpoints are defined here. The API layer's only job: validate input, call the
orchestrator, format the response. All business logic stays in the orchestrator.

### Endpoint Reference

| Method | Endpoint | Behaviour |
|--------|----------|-----------|
| `GET` | `/` | Serves `client/web/index.html` (web UI) |
| `POST` | `/synthesize` | Synchronous: runs pipeline, returns MP3 immediately |
| `POST` | `/scene` | Multi-voice scene: returns MP3 + metadata in response headers |
| `POST` | `/jobs` | Async: returns `job_id` instantly (202), runs pipeline in background |
| `GET` | `/jobs/{id}` | Poll job status and metrics |
| `GET` | `/jobs/{id}/download` | Download the completed MP3 file |
| `GET` | `/cache/stats` | Number of cached files and total disk usage |
| `DELETE` | `/cache` | Clear all cached audio files |
| `GET` | `/health` | Check internet connectivity + cache writability |

### Non-ASCII Headers — The `/scene` Encoding Problem

HTTP/1.1 headers can only carry ASCII characters (0–127). Telugu/Hindi text is Unicode and
cannot go in headers directly.

```python
# Solution: JSON → UTF-8 bytes → base64 → pure ASCII string
script_b64 = base64.b64encode(
    json.dumps(transcript, ensure_ascii=False).encode("utf-8")
).decode("ascii")

headers = {
    "X-Cast":    json.dumps(cast),      # speaker → voice ID (always ASCII-safe)
    "X-Script":  script_b64,            # Telugu/Hindi encoded as base64 ASCII
    "X-Metrics": json.dumps(metrics),   # Numbers only (ASCII-safe)
}
```

**Client reversal:** `base64.b64decode(header) → UTF-8 decode → JSON parse`

### Health Check — How It Works

```python
@router.get("/health")
def health_check():
    # Internet check: connect to Cloudflare DNS (1.1.1.1:53)
    # Port 53 is almost never firewalled. If it connects, internet is live.
    socket.socket(AF_INET, SOCK_STREAM).connect(("1.1.1.1", 53))

    # Cache check: write + delete a dummy ".health_test" file
    # If write fails → cache directory has permission issues

    return {"status": "healthy|degraded|unhealthy",
            "internet_connected": True/False,
            "cache_writable": True/False}
```

---

## 📊 STEP 12 — Quality Evaluation Layer (`eval/`)

These are **offline analysis tools** — NOT run on live requests (too slow, too heavy for
production).

### 12a. `eval/metrics.py` — Measurement Primitives

```python
def normalize_text(s: str) -> str:
    # MUST run before comparing any two texts
    s = unicodedata.normalize("NFC", s)    # Same Unicode chars, same encoding
    # Remove punctuation BUT keep Indic combining vowel signs (category "M")
    # Removing Indic vowel signs DESTROYS meaning (e.g. Telugu vowels)
    s = "".join(ch for ch in s if not unicodedata.category(ch).startswith("P"))
    s = s.lower()                           # Case-insensitive
    s = re.sub(r"\s+", " ", s).strip()     # Collapse whitespace

def calculate_cer(reference, hypothesis) -> float:
    # Character Error Rate = Levenshtein(char level) / len(reference)
    # 0.0 = identical, 1.0 = completely wrong

def calculate_wer(reference, hypothesis) -> float:
    # Word Error Rate = Levenshtein(word level) / num_words(reference)

def calculate_rtf(synthesis_time, audio_duration) -> float:
    # Real-Time Factor = synthesis_time / audio_duration
    # RTF < 1.0 = faster than real-time (Basha achieves ~0.1 RTF = 10x faster)

def calculate_semantic_similarity(reference, hypothesis) -> float:
    # Uses multilingual BERT (sentence-transformers) for meaning comparison
    # More forgiving than CER/WER: "automobile" vs "car" ≈ 0.98
    # Basha achieves 0.80-0.92 across 11 languages
```

**Why normalize before measuring?**
Without normalization: `"Hello!"` vs `"Hello"` shows as CER = 0.17 (wrong — they're the same).
Normalization makes comparisons fair and language-independent.

### 12b. `eval/asr_roundtrip.py` — Closed-Loop Evaluation

```python
def transcribe_audio_bytes(audio_bytes: bytes, lang: str) -> str:
    # Step 1: Convert MP3 to WAV (Google STT requires WAV, not MP3)
    audio_segment = AudioSegment.from_file(io.BytesIO(audio_bytes))
    wav_io = io.BytesIO()
    audio_segment.export(wav_io, format="wav")

    # Step 2: Feed WAV into Google Speech Recognition
    recognizer = sr.Recognizer()
    with sr.AudioFile(wav_io) as source:
        audio_data = recognizer.record(source)

    # Step 3: Transcribe with retry on rate-limit
    return recognizer.recognize_google(audio_data, language=lang_code)
```

**The Closed-Loop Test Logic:**
```
English input text
    → translate to Hindi
    → synthesize Hindi audio
    → transcribe Hindi audio back to text (ASR round-trip)
    → compare transcription to original Hindi translation via BERT similarity
Score: 0.80+ means 80%+ of meaning survived the full translate→speak→hear cycle
```

**What this proves:** The TTS engine says the right words intelligibly.
**What this does NOT prove:** Naturalness (whether the voice sounds human). That requires
human listeners rating audio on a Mean Opinion Score (MOS) scale.

---

## 🧪 STEP 13 — Tests (`tests/test_api.py`)

```python
# Mock the orchestrator so no real audio is synthesized in tests
@patch("basha.api.routes.orchestrator.process")
def test_synthesize_returns_audio(mock_process):
    mock_process.return_value = (b"FAKE_MP3_BYTES", {"rtf": 0.2})

    resp = client.post("/synthesize", json={"text": "Hello", "target_language": "de"})

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "audio/mpeg"
    assert resp.content == b"FAKE_MP3_BYTES"
```

**Why mock at the orchestrator level?**
- Tests run in milliseconds (no real API calls, no network).
- Tests work fully offline (no internet required, no rate limits hit).
- Tests are 100% deterministic (same fake bytes every run, never flaky).
- Tests verify **HTTP layer behavior** only: status codes, headers, content-type, error formats.

**Test coverage:**

| Test | What It Verifies |
|------|-----------------|
| `test_synthesize_returns_audio` | Happy path: 200, `audio/mpeg`, correct bytes |
| `test_synthesize_empty_audio_is_client_error` | Empty pipeline output → HTTP 400 |
| `test_synthesize_rejects_missing_text` | Missing required field → HTTP 422 |
| `test_scene_populates_headers` | X-Cast, X-Script (base64 decoded), X-Metrics correct |
| `test_cache_stats_shape` | Cache endpoint returns `cached_files`, `total_mb`, `cache_dir` |
| `test_health_shape` | Health check returns `status`, `internet_connected`, `cache_writable` |
| `test_health_degraded_without_internet` | Simulated no-internet → status `"degraded"` |

---

## 🐳 STEP 14 — Deployment (`Dockerfile`)

```dockerfile
FROM python:3.11-slim
RUN apt-get install -y ffmpeg         ← System dependency (pydub needs ffmpeg)

COPY requirements.txt .
RUN pip install -r requirements.txt   ← Installed BEFORE code is copied

COPY . .                              ← Code copied AFTER deps

CMD uvicorn basha.main:app --app-dir src --host 0.0.0.0 --port $PORT
```

**Docker layer caching — why `requirements.txt` is copied first:**

| Layer | Contents | Changes when |
|-------|----------|-------------|
| Layer 1 | OS + ffmpeg | Almost never |
| Layer 2 | `pip install` | Only when dependencies change |
| Layer 3 | `COPY . .` | Every code commit |

If you only change Python code (most common case), Docker reuses Layers 1 and 2 from cache.
The slow `pip install` step (which can take 3+ minutes) is skipped. Build time drops to ~10s.

---

## 🔁 STEP 15 — End-to-End Request Trace

Let's follow a complete request through every layer:

**Scenario:** `POST /jobs` with `text="The sun sets in the west.", target_language="hi"`

```
1. HTTP request arrives at Uvicorn (ASGI server)
   ↓
2. RequestLoggingMiddleware intercepts:
   - request_id = "abc-1234" (UUID, new per request)
   - REQUEST_ID_VAR.set("abc-1234")  ← stored in ContextVar
   - Logs: {"message": "Incoming POST /jobs", "request_id": "abc-1234"}
   ↓
3. FastAPI validates body against JobSubmitRequest:
   - text: 26 chars ✓  (min=1, max=50000)
   - target_language: "hi" ✓
   - Validation passes → handler called
   ↓
4. routes.submit_job() executes:
   - job_id = job_manager.create_job(text, "hi", voice=None)
     → UUID "d9f2c..." stored in _jobs with status="pending"
   - background_tasks.add_task(run_background_synthesis, job_id, ...)
   - Returns HTTP 202: {"job_id": "d9f2c...", "status": "pending"}
   ↓
   [Response sent to client — client gets job_id immediately]
   ↓
5. Background thread starts: run_background_synthesis()
   - REQUEST_ID_VAR.set(job_id)  ← job's own ID in all its logs
   - job_manager.start_job(job_id)  → status: "processing"
   ↓
6. orchestrator.process("The sun sets in the west.", "hi", backend="auto") called
   ↓
7. split_text_into_chunks(text, max_chars=240):
   - Only 26 chars → returns ["The sun sets in the west."]  ← 1 chunk
   ↓
8. For chunk "The sun sets in the west.":
   a. translator.translate("The sun sets in the west.", "hi")
      - "hi" != "en" → calls GoogleTranslator
      - Returns "सूर्य पश्चिम में डूबता है।"
   b. cache.get("सूर्य पश्चिम...", "hi", voice=None, backend="GTTSBackend")
      - SHA256 key computed
      - File doesn't exist → CACHE MISS → returns None
   c. GTTSBackend.synthesize("सूर्य पश्चिम...", lang="hi", voice=None)
      - Calls Google TTS API → returns MP3 bytes
      - If rate-limited: retries after 2s, then 4s
   d. cache.set("सूर्य पश्चिम...", "hi", mp3_bytes, backend="GTTSBackend")
      - Writes "audio_cache/[sha256].mp3"
   ↓
9. stitch_audio_chunks([mp3_bytes], pause_ms=150)
   - Only 1 clip → nothing to stitch → returns same bytes as MP3
   ↓
10. Metrics computed:
    - translation_time: ~0.8s
    - synthesis_time: ~1.2s
    - cache_hits: 0, total_chunks: 1, cache_savings: 0.0%
    - RTF = 2.0 / audio_duration_seconds
   ↓
11. MP3 saved: "audio_cache/job_d9f2c....mp3"
    job_manager.complete_job(job_id, "job_d9f2c....mp3", metrics)
    → status: "completed"

--- Client polls for result ---

12. GET /jobs/d9f2c...
    - job_manager.get_job("d9f2c...") → {status: "completed", download_url: ..., metrics: ...}
    - Returns 200 with full job info + metrics

13. GET /jobs/d9f2c.../download
    - Reads "audio_cache/job_d9f2c....mp3"
    - Returns FileResponse (audio/mpeg, filename="basha_narration_d9f2c....mp3")

--- If same request is made again ---

Step 8b (next time): cache.get("सूर्य पश्चिम...", "hi", None, "GTTSBackend")
→ File NOW EXISTS → CACHE HIT → skip translate + synthesize entirely
→ synthesis_time: 0s, cache_savings: 100%
```

---

## 📐 STEP 16 — Design Patterns Summary

| Pattern | Where Used | Problem It Solves |
|---------|-----------|-------------------|
| **Singleton** | `core/config.py`, `jobs/queue.py` | One global instance; config/queue loaded once |
| **Abstract Base Class** | `tts/base.py`, `translation/base.py` | All engines interchangeable |
| **Factory** | `tts/factory.py` | Engine selection without hardcoding class names |
| **Façade** | `pipeline/orchestrator.py` | Single entry point hides all pipeline complexity |
| **Content-Addressed Storage** | `core/cache.py` | Cache without lookup table; collision-proof |
| **Strategy** | `TTSBackend` implementations | Swap algorithms (gTTS/Edge-TTS) at runtime |
| **Retry with Backoff** | `tts/gtts_backend.py` | Graceful handling of API rate limits |
| **State Machine** | `jobs/queue.py` | Job lifecycle (pending→processing→completed|failed) |
| **Context Manager** | `core/logging.py` LogContext | Auto-timing + exception-aware logging |
| **ContextVar** | `core/logging.py` | Per-request ID tracing in async/concurrent code |
| **Streaming Collection** | `tts/edge_tts.py` | Memory-efficient chunked audio stream handling |

---

## 🗺️ Architecture Diagram

```
Client (Browser / curl / Python)
          │
          │  HTTP Request
          ▼
┌─────────────────────────────────┐
│  RequestLoggingMiddleware       │  ← Assigns request_id UUID, logs start+end+duration
│  (core/logging.py)              │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│  FastAPI Routes                 │  ← Validates input via Pydantic schemas
│  (api/routes.py)                │  ← Calls orchestrator (never calls TTS/translate directly)
│  (api/schemas.py)               │
└──────────────┬──────────────────┘
               │
               ▼
┌───────────────────────────────────────────────────────────────┐
│  PipelineOrchestrator  (pipeline/orchestrator.py)  ← FAÇADE  │
│                                                               │
│  process()                   process_scene()                  │
│  ┌───────────────────┐       ┌─────────────────────────────┐ │
│  │ 1. Chunker         │       │ 1. parse_dialogue()          │ │
│  │ 2. Translator      │       │ 2. guess_gender()            │ │
│  │ 3. Cache (hit/miss)│       │ 3. VoiceManager (round-robin)│ │
│  │ 4. TTSFactory      │       │ 4. Translator (per line)     │ │
│  │ 5. Stitcher        │       │ 5. Cache (hit/miss)          │ │
│  └───────────────────┘       │ 6. EdgeTTSBackend            │ │
│                               │ 7. Stitcher (300ms pauses)   │ │
│                               └─────────────────────────────┘ │
└───────────┬──────────────────────────────┬────────────────────┘
            │                              │
            ▼                              ▼
┌──────────────────────┐       ┌───────────────────────────┐
│  TTS Backends        │       │  Translation Backend       │
│  GTTSBackend         │       │  DeepTranslatorBackend     │
│  EdgeTTSBackend      │       │  (wraps Google Translate)  │
│  (via TTSFactory)    │       └───────────────────────────┘
└───────────┬──────────┘
            │
            ▼
┌──────────────────────┐
│  AudioCache          │  ← SHA-256 keyed, disk-based (.mp3 files)
│  (core/cache.py)     │
└──────────────────────┘
```

---

## ✅ Final Summary — What to Remember About Each File

| Layer | Files | One-Liner |
|-------|-------|-----------|
| **Config** | `config/*.yaml` | All runtime behaviour, change without touching Python |
| **Boot** | `main.py` | 5-step startup: log → app → middleware → routes → UI |
| **Infrastructure** | `core/` | Settings singleton, audio cache, JSON logging |
| **Contracts** | `tts/base.py`, `translation/base.py`, `api/schemas.py` | Interfaces all engines must obey |
| **Translation Engine** | `translation/deep_translator_backend.py` | Free Google Translate wrapper with English short-circuit |
| **TTS — gTTS** | `tts/gtts_backend.py` | Free, CPU, in-memory, retry-with-backoff |
| **TTS — Edge** | `tts/edge_tts.py` | Neural, streaming, gendered, async-bridged |
| **Voice Logic** | `tts/voices.py` | Round-robin, gender-aware, per-speaker assignment |
| **Engine Selection** | `tts/factory.py` | Registry pattern; add engine = 1 line change |
| **Script Parsing** | `script/parser.py`, `script/gender.py` | Split "Speaker: text", infer gender from name |
| **Pipeline Utils** | `pipeline/chunker.py`, `pipeline/stitcher.py` | Chunk text into ≤240-char pieces, join audio clips |
| **⭐ The Heart** | `pipeline/orchestrator.py` | Façade: ties everything together into one callable |
| **Job Queue** | `jobs/queue.py` | Thread-safe, 4-state machine for async long-form jobs |
| **API** | `api/routes.py` | 9 HTTP endpoints; validate → orchestrate → respond |
| **Evaluation** | `eval/metrics.py`, `eval/asr_roundtrip.py` | Offline quality tools: CER/WER/RTF/BERT similarity |
| **Tests** | `tests/test_api.py` | Mock pipeline, verify HTTP layer only; offline + fast |
| **Deploy** | `Dockerfile` | Layer-cached: deps before code = fast rebuilds |
