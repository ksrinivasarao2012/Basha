# GETTING STARTED — read this first (written for a beginner)

This file is your map. The `README.md` describes the *full, ambitious* version of
**Basha**. This file tells you what to **actually build by tomorrow morning**, in
order, and what each empty file is for. Do not try to build everything in the README.
You will build a small slice that works end-to-end and demos well.

---

## 0. CPU-only — yes, this whole project works without a GPU

You have **no GPU**, and that is completely fine. The MVP path uses `gTTS` and
`deep-translator`, which do the heavy work **on Google's servers**, not your laptop — your
machine only sends text and receives audio. So **every step in this guide runs on CPU.**
The only things that would want a GPU are the optional Tier-2 local models (Indic
Parler-TTS, XTTS, etc.) — we are **not** building those tonight. Leave them as "future work"
and talk about them in the interview.

---

## 1. The honest reality check (read this carefully)

**Can we finish by 10:00 AM?** — **Yes**, but only the *right-sized* version.

The README lists Level 0 → Level 3. The big local AI models in it (Indic Parler-TTS,
XTTS, IndicTrans2, Whisper) want a **GPU** (you don't have one), plus multi-gigabyte
downloads and hours of fighting with installs. With no GPU, limited time, and limited
experience, **chasing those will make you fail.** So we deliberately scope down to the
CPU-only, cloud-backed path.

**What you WILL build tonight (achievable, impressive enough):**

- A real **FastAPI web service** with a `/synthesize` endpoint and auto docs.
- A **free TTS path** using `gTTS` (no GPU, no API key, just internet).
- A **free translation path** using `deep-translator` (English → Telugu/Tamil/German…).
- The **pipeline**: text → translate → speak → return audio.
- A tiny **Streamlit page** so you can paste text and hear the result in a browser.
- A **cache** + **clause-aware chunking** (these are easy and make it look professional).
- One or two **tests**.

That hits "Level 0" fully and a good chunk of "Level 1" in the README — which is exactly
the line the README calls *"a script vs. thinks like someone who ships."*

**What you will NOT build tonight (talk about it instead):**

- Local GPU models, the ASR evaluation gate, voice cloning, Docker, job queues.
- In the interview you *describe* these as "what I'd do next" — the README literally says
  that is the signal they want. Building Level 1 cleanly + explaining Level 2/3 wins.

> **The one improvement I made to the plan:** the README's default backend is the heavy
> local models. For your situation I flipped the default to **gTTS + deep-translator**
> (already set in `config/config.yaml`). It is 100% free, installs in 2 minutes, needs no
> GPU, and demos identically. The model-swapping *architecture* stays — you just plug the
> heavy models in later as a bonus. This is the single most important change.

---

## 2. Why this project fits the job (your interview story)

The JD ("Gen AI Development Intern" at Pocket FM) says: *"expanding Text-to-Speech
capabilities across multiple languages… European languages (German, French, Spanish,
Italian, Portuguese) and Indian regional languages (Tamil, Telugu, Malayalam, Kannada,
Marathi)."*

**Basha is exactly that:** a multilingual text-to-speech + localization service. You are
not building a toy — you are building a small version of the thing their team builds. That
is the strongest possible project to show up with. Memorize this one-line pitch:

> *"Basha is a multilingual TTS service: paste text, it localizes to a target language and
> narrates it, behind a clean swappable-backend API so a free engine or a GPU model can be
> dropped in without touching the pipeline."*

---

## 3. The few things you need to learn (and only these)

You said you'll learn a few things — here is the short list. Spend ~20 min on each:

1. **What an API / FastAPI is** — a program that listens for web requests and replies.
   You define a function, decorate it with `@app.post("/synthesize")`, and it's an endpoint.
2. **What a Python virtual environment is** — an isolated box for this project's packages
   so installs don't break anything else.
3. **What "text-to-speech" and "translation" libraries do** — `gTTS` turns text into an
   MP3; `deep-translator` turns English text into another language's text.
4. **What Streamlit is** — turns a short Python script into a web page with buttons.

That's genuinely all you need to understand to ship the MVP. Everything else in the
README is vocabulary you can *talk* about, not build.

---

## 4. Setup (do this once, ~10 minutes)

Open PowerShell in this `D:\Basha` folder and run:

```powershell
# 1. Create an isolated environment
python -m venv .venv

# 2. Activate it (you'll see "(.venv)" appear at the start of the line)
.\.venv\Scripts\Activate.ps1

# 3. Install ONLY the Tier-1 packages (fast, no GPU)
pip install fastapi "uvicorn[standard]" pydantic pydantic-settings python-multipart pyyaml streamlit gtts deep-translator pydub soundfile numpy requests python-dotenv pytest httpx
```

> **ffmpeg note:** `pydub` (audio stitching) needs `ffmpeg`. If stitching errors out,
> install it: `winget install Gyan.FFmpeg` then restart PowerShell. For the very first
> demo you can skip stitching and just return a single clip — so don't get stuck here.

If `python` isn't found, install Python 3.11 from python.org first (tick "Add to PATH").

---

## 5. Build order — do the files in THIS sequence

Each empty file already exists. Fill them in this order. Do not skip ahead; each step
gives you something you can run and see working. Ask me (Claude) to write any single file
when you reach it — go one file at a time so you understand each piece.

> ⚠️ **Before you write files 7, 8, and 10, skim [`docs/PITFALLS.md`](docs/PITFALLS.md).**
> It has 6 real CPU/Windows traps and the exact decision for each (SHA-256 cache key, sync
> `def` routes, rate-limit sleeps, skipping ffmpeg). These are baked into the table below.

| # | File | What to put in it | You can run it after? |
|---|------|-------------------|-----------------------|
| 1 | `src/basha/tts/base.py` | An abstract class `TTSBackend` with one method `synthesize(text, lang) -> audio bytes`. The "contract" every engine follows. | no |
| 2 | `src/basha/tts/gtts_backend.py` | A `GTTSBackend(TTSBackend)` that calls `gTTS` and returns MP3 bytes. | yes (tiny script) |
| 3 | `src/basha/translation/base.py` | Abstract `TranslationBackend` with `translate(text, target_lang) -> str`. | no |
| 4 | `src/basha/translation/deep_translator_backend.py` | Wraps `deep-translator`'s GoogleTranslator. | yes |
| 5 | `src/basha/pipeline/chunker.py` | A function that splits long text into <240-char pieces on sentence/comma boundaries. | yes |
| 6 | `src/basha/pipeline/stitcher.py` | Joins multiple audio clips into one (with `pydub`) + small pauses. | yes |
| 7 | `src/basha/pipeline/orchestrator.py` | The glue: `chunk text -> translate each -> JOIN translated text -> ONE gTTS call`. Returns final audio. **This is the heart.** (See `docs/PITFALLS.md` #3, #4.) | yes |
| 8 | `src/basha/core/cache.py` | File cache keyed on **SHA-256** of `text+lang+voice` (NOT `hash()` — see `docs/PITFALLS.md` #1). | yes |
| 9 | `src/basha/api/schemas.py` | Pydantic models: `SynthesizeRequest{text, target_language}` + response shape. | no |
| 10 | `src/basha/api/routes.py` | The `/synthesize`, `/health`, `/backends` endpoints. Use **sync `def`**, not `async def` (see `docs/PITFALLS.md` #2). | no |
| 11 | `src/basha/main.py` | Creates the FastAPI `app` and includes the routes. | **YES — service is live** |
| 12 | `client/streamlit_app.py` | A text box + "Synthesize" button that POSTs to the API and plays the audio. | **YES — full demo** |
| 13 | `src/basha/tts/factory.py` | Reads `config.yaml`, returns the chosen backend. (Makes it "swappable".) | yes |
| 14 | `tests/test_chunker.py` | A couple of asserts on the chunker. Proves you test. | yes |

**The "you're done and safe" checkpoint is after step 12.** Steps 13–14 are polish that
make it look professional — do them if time allows. Everything below (Indic Parler, XTTS,
the eval gate, Docker, jobs) is **optional stretch**; leave those files empty and mention
them as "designed for, not yet implemented" — the architecture already has slots for them.

---

## 6. How to run what you build

```powershell
# Terminal 1 — start the API (from D:\Basha, venv activated)
uvicorn src.basha.main:app --reload --port 8000
# then open http://localhost:8000/docs  -> you get clickable auto-generated API docs

# Terminal 2 — start the demo UI (activate venv here too)
streamlit run client/streamlit_app.py
```

---

## 7. Languages to demo (copy these codes)

| Code | Language | Family |
|------|----------|--------|
| `te` | Telugu | Indian |
| `ta` | Tamil | Indian |
| `kn` | Kannada | Indian |
| `ml` | Malayalam | Indian |
| `mr` | Marathi | Indian |
| `hi` | Hindi | Indian |
| `de` | German | European |
| `fr` | French | European |
| `es` | Spanish | European |
| `it` | Italian | European |
| `pt` | Portuguese | European |

gTTS supports all of these for free. Demo one Indian + one European language to mirror the
JD exactly. Put 2–3 example texts in `samples/input/` and the generated audio in
`samples/output/` so the project isn't empty when someone clones it.

---

## 8. Your timeline tonight (suggested)

| Time | Goal |
|------|------|
| now → +30 min | Read §1–§3, do §4 setup, confirm `gtts` makes an mp3 in a 3-line test |
| +30 → +90 min | Steps 1–7 (backends + pipeline). Ask me file-by-file. |
| +90 → +150 min | Steps 8–12 (cache, API, Streamlit) → **full working demo** |
| +150 → +200 min | Add 2 sample inputs/outputs, write tests (13–14), update README screenshots |
| buffer | Practice saying the §2 pitch out loud 3 times |

If you fall behind, **stop at step 12** — a working text→translate→speak demo is a complete,
defensible project. Polish is optional; a working demo is not.

---

## 9. What to do RIGHT NOW

1. Do the §4 setup.
2. Come back and tell me: **"done setup, write file 1"** — I'll write `tts/base.py` and
   explain every line, then we go down the table one file at a time.

You've got this. The scope is right-sized for the time you have.
