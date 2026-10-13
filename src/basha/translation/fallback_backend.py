"""
Translation with automatic fallback + caching.

Why this exists
---------------
`deep-translator`'s GoogleTranslator calls Google's *unofficial* web endpoint.
Google answers "too many requests" (HTTP 429) for shared cloud IPs such as
Render's free tier, so every translation (and therefore every audio job) failed.

This backend tries a list of providers in order (Google first, then MyMemory),
remembers which one is currently failing so it is skipped for a while, and caches
every successful translation so the same text is never translated twice.
"""
import hashlib
import os
import re
import threading
import time
from collections import OrderedDict
from typing import Callable, Dict, List, Optional, Tuple

import requests

from basha.core.logging import get_logger
from basha.translation.base import TranslateBackend
from basha.translation.deep_translator_backend import DeepTranslatorBackend

logger = get_logger("basha.translation")

# MyMemory wants RFC-3066 style codes ("te-IN"), the same ones deep-translator uses.
_MYMEMORY_CODES = {
    "en": "en-GB", "hi": "hi-IN", "te": "te-IN", "ta": "ta-IN", "kn": "kn-IN",
    "ml": "ml-IN", "mr": "mr-IN", "de": "de-DE", "fr": "fr-FR", "es": "es-ES",
    "it": "it-IT", "pt": "pt-BR",
}

_MYMEMORY_URL = "https://api.mymemory.translated.net/get"
_MYMEMORY_MAX_CHARS = 450  # API limit is 500 bytes per request; stay safely under it.


class TranslationError(RuntimeError):
    """A provider (or every provider) failed.

    `cooldown` (seconds) lets a provider say how long it should be skipped, e.g. an
    exhausted monthly quota should not be retried every few minutes.
    """

    def __init__(self, message: str, cooldown: Optional[float] = None):
        super().__init__(message)
        self.cooldown = cooldown


def _split_for_limit(text: str, limit: int) -> List[str]:
    """Split text on sentence/word boundaries into pieces of at most `limit` chars."""
    text = text.strip()
    if len(text) <= limit:
        return [text]
    pieces, current = [], ""
    for sentence in re.split(r"(?<=[.?!;,])\s+", text):
        while len(sentence) > limit:  # a single over-long sentence: split on words
            cut = sentence.rfind(" ", 0, limit)
            cut = cut if cut > 0 else limit
            if current:
                pieces.append(current)
                current = ""
            pieces.append(sentence[:cut].strip())
            sentence = sentence[cut:].strip()
        if current and len(current) + 1 + len(sentence) > limit:
            pieces.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        pieces.append(current)
    return pieces


def mymemory_translate(text: str, target_lang: str, timeout: float = 10.0) -> str:
    """Translate English `text` with the free MyMemory API. Raises on any problem."""
    target = _MYMEMORY_CODES.get(target_lang.lower())
    if not target:
        raise TranslationError(f"MyMemory: unsupported language '{target_lang}'")

    out = []
    for piece in _split_for_limit(text, _MYMEMORY_MAX_CHARS):
        params = {"q": piece, "langpair": f"{_MYMEMORY_CODES['en']}|{target}"}
        email = os.getenv("MYMEMORY_EMAIL")  # optional: raises the free daily limit
        if email:
            params["de"] = email
        resp = requests.get(_MYMEMORY_URL, params=params, timeout=timeout)
        if resp.status_code != 200:
            raise TranslationError(f"MyMemory: HTTP {resp.status_code}")
        data = resp.json()
        # MyMemory reports quota problems INSIDE a 200 response, and puts a warning
        # sentence in translatedText. Never let that sentence be spoken as a translation.
        status = str(data.get("responseStatus", 200))
        translated = (data.get("responseData") or {}).get("translatedText") or ""
        if status != "200" or "MYMEMORY WARNING" in translated.upper() or not translated.strip():
            raise TranslationError(f"MyMemory: status {status} {translated[:80]!r}", cooldown=3600.0)
        out.append(translated.strip())
    return " ".join(out)


_AZURE_DEFAULT_ENDPOINT = "https://api.cognitive.microsofttranslator.com"
# Azure uses the same short codes Basha uses (te, hi, ta, ...). "pt" = Brazilian Portuguese.


def azure_translate(text: str, target_lang: str, timeout: float = 10.0) -> str:
    """Translate English `text` with Azure AI Translator (official API, needs a key).

    Reads AZURE_TRANSLATOR_KEY, AZURE_TRANSLATOR_REGION and (optionally)
    AZURE_TRANSLATOR_ENDPOINT from the environment. On the free F0 tier, Azure answers
    HTTP 403 once the monthly quota is used up -- we treat that as "skip me for a while".
    """
    key = os.getenv("AZURE_TRANSLATOR_KEY")
    if not key:
        raise TranslationError("Azure: AZURE_TRANSLATOR_KEY is not set", cooldown=3600.0)
    endpoint = (os.getenv("AZURE_TRANSLATOR_ENDPOINT") or _AZURE_DEFAULT_ENDPOINT).rstrip("/")
    headers = {
        "Ocp-Apim-Subscription-Key": key,
        "Content-Type": "application/json; charset=UTF-8",
    }
    region = os.getenv("AZURE_TRANSLATOR_REGION")
    if region:
        headers["Ocp-Apim-Subscription-Region"] = region

    resp = requests.post(
        f"{endpoint}/translate",
        params={"api-version": "3.0", "from": "en", "to": target_lang.lower()},
        headers=headers,
        json=[{"Text": text}],
        timeout=timeout,
    )
    if resp.status_code in (403, 429):  # free quota used up / throttled
        raise TranslationError(f"Azure: HTTP {resp.status_code} (quota or rate limit)", cooldown=3600.0)
    if resp.status_code != 200:
        raise TranslationError(f"Azure: HTTP {resp.status_code}")
    try:
        return resp.json()[0]["translations"][0]["text"]
    except (KeyError, IndexError, TypeError, ValueError) as e:
        raise TranslationError(f"Azure: unexpected response ({e})")


class FallbackTranslator(TranslateBackend):
    """Try providers in order, skip ones that recently failed, cache every result."""

    def __init__(
        self,
        providers: Optional[List[Tuple[str, Callable[[str, str], str]]]] = None,
        cooldown_seconds: float = 300.0,
        max_cache_entries: int = 5000,
        clock: Callable[[], float] = time.monotonic,
    ):
        if providers is None:
            google = DeepTranslatorBackend()
            providers = []
            if os.getenv("AZURE_TRANSLATOR_KEY"):  # official API first, only if configured
                providers.append(("azure", azure_translate))
            providers += [("google", google.translate), ("mymemory", mymemory_translate)]
        self.providers = providers
        self.cooldown_seconds = cooldown_seconds
        self.max_cache_entries = max_cache_entries
        self._clock = clock
        self._blocked_until: Dict[str, float] = {}
        self._cache: "OrderedDict[str, str]" = OrderedDict()
        self._lock = threading.Lock()
        self.last_provider: Optional[str] = None

    @staticmethod
    def _key(text: str, lang: str) -> str:
        return hashlib.sha256(f"{text.strip()}:{lang.lower()}".encode("utf-8")).hexdigest()

    def translate(self, text: str, target_lang: str) -> str:
        if target_lang.lower() == "en" or not text.strip():
            return text

        key = self._key(text, target_lang)
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]

        errors = []
        now = self._clock()
        # Providers that are cooling down go last, so they are only tried if nothing else works.
        ordered = sorted(
            self.providers, key=lambda p: self._blocked_until.get(p[0], 0.0) > now
        )
        for name, fn in ordered:
            try:
                result = fn(text, target_lang)
                if not result or not result.strip():
                    raise TranslationError("empty translation")
            except Exception as e:  # any failure -> try the next provider
                cooldown = getattr(e, "cooldown", None) or self.cooldown_seconds
                with self._lock:
                    self._blocked_until[name] = self._clock() + cooldown
                errors.append(f"{name}: {str(e)[:120]}")
                logger.warning(f"Translation provider '{name}' failed ({e}); trying next")
                continue
            with self._lock:
                self._blocked_until.pop(name, None)
                self._cache[key] = result
                if len(self._cache) > self.max_cache_entries:
                    self._cache.popitem(last=False)
                self.last_provider = name
            return result

        raise TranslationError("All translation providers failed -> " + " | ".join(errors))
