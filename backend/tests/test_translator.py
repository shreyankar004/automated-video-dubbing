from app.models.job import TranscriptSegment
from app.services import translator


class FakeProvider(translator.TranslationProvider):
    def __init__(self):
        self.calls = []

    def translate(self, text: str, source_language: str) -> str:
        self.calls.append((text, source_language))
        return f"[EN:{source_language}] {text}"


def test_translate_segments_calls_provider_for_each_segment(monkeypatch):
    fake = FakeProvider()
    monkeypatch.setattr(translator, "get_provider", lambda *_: fake)

    segments = [
        TranscriptSegment(index=0, start=0.0, end=2.0, text="hallo welt"),
        TranscriptSegment(index=1, start=2.0, end=4.0, text="wie geht es dir"),
    ]

    seen_progress = []
    translator.translate_segments(
        segments, "de", "web", "unused-model",
        on_progress=lambda frac, msg: seen_progress.append(frac),
    )

    assert segments[0].translated_text == "[EN:de] hallo welt"
    assert segments[1].translated_text == "[EN:de] wie geht es dir"
    assert len(fake.calls) == 2
    assert seen_progress[-1] == 1.0


def test_get_provider_rejects_unknown_name():
    try:
        translator.get_provider("bogus", "model")
        assert False, "expected TranslationError"
    except translator.TranslationError:
        pass
