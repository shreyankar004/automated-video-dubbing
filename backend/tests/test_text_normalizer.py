from app.services.text_normalizer import normalize_for_speech


def test_removes_filler_words():
    result = normalize_for_speech("um, so basically uh this is the plan")
    assert "um" not in result.lower().split()
    assert "uh" not in result.lower().split()


def test_collapses_repeated_punctuation():
    assert normalize_for_speech("really?!?!") == "really?"


def test_adds_terminal_punctuation_when_missing():
    result = normalize_for_speech("this has no ending")
    assert result.endswith((".", "!", "?"))


def test_empty_input_returns_empty():
    assert normalize_for_speech("") == ""


def test_collapses_whitespace():
    assert normalize_for_speech("too    many     spaces") == "too many spaces."
