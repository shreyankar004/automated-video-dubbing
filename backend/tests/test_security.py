import pytest

from app.core.security import InvalidYouTubeURLError, is_youtube_url, sanitize_filename, validate_youtube_url


@pytest.mark.parametrize("url", [
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "https://youtu.be/dQw4w9WgXcQ",
    "https://m.youtube.com/watch?v=dQw4w9WgXcQ&t=10s",
    "https://www.youtube.com/shorts/dQw4w9WgXcQ",
])
def test_valid_youtube_urls(url):
    assert is_youtube_url(url) is True
    assert validate_youtube_url(url) == url


@pytest.mark.parametrize("url", [
    "https://vimeo.com/12345",
    "not a url",
    "ftp://youtube.com/watch?v=abc",
    "https://youtube.com/",
    "",
    "https://evil.com/youtube.com/watch?v=abc",
])
def test_invalid_youtube_urls(url):
    assert is_youtube_url(url) is False
    with pytest.raises(InvalidYouTubeURLError):
        validate_youtube_url(url)


def test_sanitize_filename_strips_traversal_and_separators():
    assert "/" not in sanitize_filename("../../etc/passwd")
    assert "/" not in sanitize_filename("some/../path")
    assert "\\" not in sanitize_filename("some\\path")


def test_sanitize_filename_keeps_readable_characters():
    result = sanitize_filename("My Video: Part 1 (Hindi)!.mp4")
    assert result
    assert " " not in result
    assert ":" not in result


def test_sanitize_filename_never_empty():
    assert sanitize_filename("...") == "file"
    assert sanitize_filename("") == "file"


def test_sanitize_filename_respects_max_length():
    long_name = "a" * 500
    assert len(sanitize_filename(long_name, max_length=50)) == 50
