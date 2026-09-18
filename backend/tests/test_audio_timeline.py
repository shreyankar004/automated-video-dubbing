from pathlib import Path

from app.models.job import TranscriptSegment
from app.services import audio_timeline, ffmpeg_service, tts


def _touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"fake-audio")
    return path


def test_build_segment_audio_speeds_up_overlong_speech(tmp_path, monkeypatch):
    
    durations = iter([4.0, 2.0])  

    monkeypatch.setattr(tts, "synthesize", lambda text, voice, out: _touch(out))
    monkeypatch.setattr(ffmpeg_service, "probe_duration", lambda p: next(durations))
    monkeypatch.setattr(ffmpeg_service, "change_tempo", lambda inp, out, factor: _touch(out))

    segment = TranscriptSegment(index=0, start=0.0, end=2.0, text="hello", translated_text="hello there")
    clip = audio_timeline.build_segment_audio(segment, "en-US-AriaNeural", tmp_path, max_speed_factor=1.35)

    assert clip.speed_factor == 1.35  
    assert clip.target_duration == 2.0


def test_build_segment_audio_pads_short_speech_with_silence(tmp_path, monkeypatch):
    
    monkeypatch.setattr(tts, "synthesize", lambda text, voice, out: _touch(out))
    monkeypatch.setattr(ffmpeg_service, "probe_duration", lambda p: 1.0)
    monkeypatch.setattr(ffmpeg_service, "generate_silence", lambda dur, out, sample_rate=24000: _touch(out))
    monkeypatch.setattr(ffmpeg_service, "concat_audio_segments", lambda paths, out: _touch(out))

    segment = TranscriptSegment(index=1, start=0.0, end=3.0, text="hi", translated_text="hi")
    clip = audio_timeline.build_segment_audio(segment, "en-US-AriaNeural", tmp_path, max_speed_factor=1.35)

    assert clip.speed_factor == 1.0
    assert clip.actual_duration == 3.0
