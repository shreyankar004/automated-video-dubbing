from __future__ import annotations

from abc import ABC, abstractmethod
from functools import lru_cache
import time

from app.core.logging import get_logger

logger = get_logger(__name__)


class TranslationError(RuntimeError):
    pass


class TranslationProvider(ABC):
    """Contract every translation backend must satisfy."""

    @abstractmethod
    def translate(self, text: str, source_language: str) -> str:
        """Translate `text` (in `source_language`) into natural English."""


class LocalNLLBProvider(TranslationProvider):
    """Offline translation using Meta's NLLB-200 model via transformers.

    Chosen as the default local/free path because a single checkpoint covers
    every language Whisper can detect, including Indian languages, without
    a paid API. Swap `model_name` for a smaller/larger checkpoint as needed.
    """

    # Whisper ISO-639-1 codes -> NLLB FLORES-200 codes (subset covering common cases).
    _LANG_MAP = {
        "en": "eng_Latn", "hi": "hin_Deva", "bn": "ben_Beng", "de": "deu_Latn",
        "fr": "fra_Latn", "es": "spa_Latn", "pt": "por_Latn", "ru": "rus_Cyrl",
        "ja": "jpn_Jpan", "zh": "zho_Hans", "ar": "arb_Arab", "ta": "tam_Taml",
        "te": "tel_Telu", "mr": "mar_Deva", "gu": "guj_Gujr", "ur": "urd_Arab",
        "it": "ita_Latn", "ko": "kor_Hang", "tr": "tur_Latn", "nl": "nld_Latn",
    }

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._pipeline = None

    def _load(self):
        if self._pipeline is not None:
            return self._pipeline
        try:
            from transformers import pipeline
        except ImportError as exc:
            raise TranslationError("transformers is not installed for local translation") from exc
        logger.info("Loading local translation model %s", self.model_name)
        self._pipeline = pipeline("translation", model=self.model_name)
        return self._pipeline

    def translate(self, text: str, source_language: str) -> str:
        src_code = self._LANG_MAP.get(source_language, "eng_Latn")
        translator = self._load()
        try:
            result = translator(text, src_lang=src_code, tgt_lang="eng_Latn", max_length=400)
            return result[0]["translation_text"].strip()
        except Exception as exc:
            raise TranslationError(f"Local translation failed: {exc}") from exc


class WebFreeProvider(TranslationProvider):
    """Free web-based translation (no API key) via the `deep-translator` package.

    Used as the pragmatic default: it needs no local GPU/large model download,
    which keeps the assignment runnable on ordinary laptops. The underlying
    endpoint enforces an unofficial rate limit, so calls are retried with
    exponential backoff on rate-limit errors.
    """

    _RATE_LIMIT_MARKERS = ("too many requests", "429")
    _MAX_ATTEMPTS = 8
    _BASE_DELAY_SECONDS = 3.0

    def __init__(self) -> None:
        self._client_cls = None

    def _load(self):
        if self._client_cls is not None:
            return self._client_cls
        try:
            from deep_translator import GoogleTranslator
        except ImportError as exc:
            raise TranslationError("deep-translator is not installed") from exc
        self._client_cls = GoogleTranslator
        return self._client_cls

    def translate(self, text: str, source_language: str) -> str:
        GoogleTranslator = self._load()
        last_error: Exception | None = None
        for attempt in range(1, self._MAX_ATTEMPTS + 1):
            try:
                translator = GoogleTranslator(source="auto", target="en")
                return translator.translate(text).strip()
            except Exception as exc:  # noqa: BLE001 - retried below, re-raised after
                last_error = exc
                message = str(exc).lower()
                is_rate_limited = any(marker in message for marker in self._RATE_LIMIT_MARKERS)
                if not is_rate_limited or attempt == self._MAX_ATTEMPTS:
                    break
                delay = self._BASE_DELAY_SECONDS * (2 ** (attempt - 1))
                logger.warning(
                    "Translation rate-limited (attempt %s/%s), retrying in %.1fs",
                    attempt, self._MAX_ATTEMPTS, delay,
                )
                time.sleep(delay)
        raise TranslationError(f"Web translation failed: {last_error}") from last_error


@lru_cache
def get_provider(provider_name: str, model_name: str) -> TranslationProvider:
    if provider_name == "local":
        return LocalNLLBProvider(model_name)
    if provider_name == "web":
        return WebFreeProvider()
    raise TranslationError(f"Unknown translation provider '{provider_name}'")


def translate_segments(
    segments,
    source_language: str,
    provider_name: str,
    model_name: str,
    on_progress=None,
    inter_segment_delay: float = 2.0,
):
    provider = get_provider(provider_name, model_name)
    total = len(segments) or 1
    for i, segment in enumerate(segments):
        segment.translated_text = provider.translate(segment.text, source_language)
        if on_progress:
            on_progress((i + 1) / total, f"Translated segment {i + 1}/{total}")
        if provider_name == "web" and i < len(segments) - 1:
            time.sleep(inter_segment_delay)
    return segments
