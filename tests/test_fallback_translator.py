"""Offline tests for the Google -> MyMemory fallback translator (no network needed)."""
import pytest
from unittest.mock import patch, MagicMock

from basha.translation.fallback_backend import (
    FallbackTranslator, TranslationError, mymemory_translate, azure_translate, _split_for_limit,
)


class Counter:
    def __init__(self, result=None, error=None):
        self.result, self.error, self.calls = result, error, 0

    def __call__(self, text, lang):
        self.calls += 1
        if self.error:
            raise self.error
        return self.result or f"{lang}:{text}"


def make(google, mymemory, clock=None):
    kwargs = {"clock": clock} if clock else {}
    return FallbackTranslator(providers=[("google", google), ("mymemory", mymemory)], **kwargs)


def test_google_used_when_it_works():
    g, m = Counter(result="G"), Counter(result="M")
    t = make(g, m)
    assert t.translate("hello", "te") == "G"
    assert (g.calls, m.calls) == (1, 0)


def test_falls_back_when_google_blocked():
    g, m = Counter(error=RuntimeError("429 too many requests")), Counter(result="M")
    t = make(g, m)
    assert t.translate("hello", "te") == "M"
    assert t.last_provider == "mymemory"


def test_result_is_cached():
    g, m = Counter(error=RuntimeError("429")), Counter(result="M")
    t = make(g, m)
    t.translate("hello", "te")
    t.translate("hello", "te")  # e.g. the second translate call made by the /jobs route
    assert m.calls == 1 and g.calls == 1


def test_failed_provider_is_skipped_during_cooldown_then_retried():
    now = [0.0]
    g, m = Counter(error=RuntimeError("429")), Counter(result="M")
    t = make(g, m, clock=lambda: now[0])
    t.translate("one", "te")
    t.translate("two", "te")           # Google cooling down -> not called again
    assert g.calls == 1
    now[0] += 301                      # cooldown over
    g.error, g.result = None, "G"
    assert t.translate("three", "te") == "G"
    assert g.calls == 2


def test_all_providers_fail_raises_clear_error():
    t = make(Counter(error=RuntimeError("a")), Counter(error=RuntimeError("b")))
    with pytest.raises(TranslationError) as exc:
        t.translate("hello", "te")
    assert "google" in str(exc.value) and "mymemory" in str(exc.value)


def test_english_is_passthrough():
    g, m = Counter(), Counter()
    assert make(g, m).translate("hello", "en") == "hello"
    assert g.calls == m.calls == 0


def _resp(status=200, body=None):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = body
    return r


def test_mymemory_happy_path():
    body = {"responseStatus": 200, "responseData": {"translatedText": "నమస్తే"}}
    with patch("basha.translation.fallback_backend.requests.get", return_value=_resp(200, body)) as get:
        assert mymemory_translate("Hello", "te") == "నమస్తే"
    assert get.call_args.kwargs["params"]["langpair"] == "en-GB|te-IN"


def test_mymemory_quota_warning_is_not_returned_as_translation():
    body = {"responseStatus": 429,
            "responseData": {"translatedText": "MYMEMORY WARNING: YOU USED ALL AVAILABLE FREE TRANSLATIONS FOR TODAY."}}
    with patch("basha.translation.fallback_backend.requests.get", return_value=_resp(200, body)):
        with pytest.raises(TranslationError):
            mymemory_translate("Hello", "te")


def test_mymemory_quota_warning_even_with_status_200():
    body = {"responseStatus": 200, "responseData": {"translatedText": "MYMEMORY WARNING: quota"}}
    with patch("basha.translation.fallback_backend.requests.get", return_value=_resp(200, body)):
        with pytest.raises(TranslationError):
            mymemory_translate("Hello", "te")


def test_mymemory_http_error_and_unsupported_language():
    with patch("basha.translation.fallback_backend.requests.get", return_value=_resp(500, {})):
        with pytest.raises(TranslationError):
            mymemory_translate("Hello", "te")
    with pytest.raises(TranslationError):
        mymemory_translate("Hello", "xx")


def test_long_text_is_split_under_the_limit():
    text = ("This is a sentence that is fairly long. " * 40).strip()
    pieces = _split_for_limit(text, 450)
    assert len(pieces) > 1 and all(len(p) <= 450 for p in pieces)
    assert " ".join(pieces).split() == text.split()   # nothing lost

    body = {"responseStatus": 200, "responseData": {"translatedText": "x"}}
    with patch("basha.translation.fallback_backend.requests.get", return_value=_resp(200, body)) as get:
        mymemory_translate(text, "hi")
    assert get.call_count == len(pieces)


# ---------------- Azure ----------------
def test_azure_happy_path(monkeypatch):
    monkeypatch.setenv("AZURE_TRANSLATOR_KEY", "k")
    monkeypatch.setenv("AZURE_TRANSLATOR_REGION", "centralindia")
    body = [{"translations": [{"text": "నమస్తే", "to": "te"}]}]
    with patch("basha.translation.fallback_backend.requests.post", return_value=_resp(200, body)) as post:
        assert azure_translate("Hello", "te") == "నమస్తే"
    kw = post.call_args.kwargs
    assert kw["params"] == {"api-version": "3.0", "from": "en", "to": "te"}
    assert kw["headers"]["Ocp-Apim-Subscription-Key"] == "k"
    assert kw["headers"]["Ocp-Apim-Subscription-Region"] == "centralindia"
    assert kw["json"] == [{"Text": "Hello"}]


def test_azure_quota_exhausted_gives_long_cooldown(monkeypatch):
    monkeypatch.setenv("AZURE_TRANSLATOR_KEY", "k")
    with patch("basha.translation.fallback_backend.requests.post", return_value=_resp(403, {})):
        with pytest.raises(TranslationError) as exc:
            azure_translate("Hello", "te")
    assert exc.value.cooldown == 3600.0


def test_azure_missing_key_raises(monkeypatch):
    monkeypatch.delenv("AZURE_TRANSLATOR_KEY", raising=False)
    with pytest.raises(TranslationError):
        azure_translate("Hello", "te")


def test_azure_only_in_default_providers_when_key_set(monkeypatch):
    monkeypatch.delenv("AZURE_TRANSLATOR_KEY", raising=False)
    assert [n for n, _ in FallbackTranslator().providers] == ["google", "mymemory"]
    monkeypatch.setenv("AZURE_TRANSLATOR_KEY", "k")
    assert [n for n, _ in FallbackTranslator().providers] == ["azure", "google", "mymemory"]


def test_provider_cooldown_length_comes_from_the_error():
    now = [0.0]
    az = Counter(error=TranslationError("quota", cooldown=3600.0))
    t = FallbackTranslator(providers=[("azure", az), ("mymemory", Counter(result="M"))], clock=lambda: now[0])
    t.translate("one", "te")
    now[0] += 600                      # past the default 5 min, still inside 1 h
    t.translate("two", "te")
    assert az.calls == 1
    now[0] += 3100                     # past 1 h
    t.translate("three", "te")
    assert az.calls == 2
