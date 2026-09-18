# DubFlow — Automated Video Dubbing System

Turns a YouTube video in any spoken language into an English-dubbed MP4:
same video, English audio, natural voice, meaning-preserving translation.

## Features

- Accepts a YouTube URL (CLI argument, interactive prompt, or web form)
- Downloads video with `yt-dlp`
- Transcribes speech with `faster-whisper`, with automatic language detection
  and CPU/GPU selection
- Translates to natural English (not word-for-word) behind a swappable
  `TranslationProvider` interface
- Synthesizes English speech with `edge-tts`
- Time-aligns each dubbed segment to the original timestamps, speeding up
  overlong speech (capped, to avoid "chipmunk" audio) and padding short
  speech with silence
- Muxes the dubbed audio back onto the **original video stream without
  re-encoding it** (`-c:v copy`)
- Job-based FastAPI backend with live progress over WebSocket
- CLI for direct, scriptable use
- Static web frontend (no build step) showing pipeline stage, detected
  language, transcript preview, and a download link

## Architecture

```
backend/app/
  core/        settings, logging, URL/filename validation
  models/      Job, JobStage, TranscriptSegment
  schemas/     Pydantic request/response models
  services/    downloader, transcriber, translator, tts, text_normalizer,
               audio_timeline, ffmpeg_service, pipeline (orchestrator)
  workers/     JobManager — runs the pipeline in a background thread
  api/         FastAPI routes + progress WebSocket
  main.py      FastAPI app, mounts the static frontend
cli/cli.py     CLI entry point, reuses the same pipeline module
frontend/      single-file dashboard (HTML/CSS/JS)
```

The CLI and the API call the **same** `app.services.pipeline.run_pipeline`
function, so behavior is identical whichever entry point you use.

### Pipeline

```
YouTube URL → validate → yt-dlp download → ffmpeg audio extraction →
faster-whisper transcription (+ language detection) → translation to
English → text normalization → edge-tts synthesis → per-segment timing
adjustment (speed-up / silence padding) → ffmpeg concat → ffmpeg mux
(video copy, new audio) → final MP4
```

## Prerequisites

- Python 3.11+
- **FFmpeg** on PATH (`ffmpeg -version` should work)
  - macOS: `brew install ffmpeg`
  - Ubuntu/Debian: `sudo apt install ffmpeg`
  - Windows: `winget install Gyan.FFmpeg` (or download a static build and add it to PATH)
- Node.js is **not required** — the frontend is a static file served by the backend.

## Setup

```bash
git clone <this repo>
cd automated-video-dubbing
./scripts/setup.sh          # Linux/macOS
# or
scripts\setup_windows.ps1   # Windows (PowerShell)
```

This creates a virtualenv, installs `backend/requirements.txt`, creates the
`data/` working directories, and copies `.env.example` to `.env`.

## Running

**Web app:**

```bash
source .venv/bin/activate
uvicorn app.main:app --reload --app-dir backend
```

Open `http://127.0.0.1:8000` — paste a YouTube URL and click **Start dubbing**.

**CLI:**

```bash
python cli/cli.py "https://www.youtube.com/watch?v=VIDEO_ID"
# or interactively:
python cli/cli.py
Enter YouTube URL: https://www.youtube.com/watch?v=VIDEO_ID
```

Example CLI output:

```
[01/06] Downloading video... (12%)
[02/06] Extracting audio... (22%)
[03/06] Transcribing... (35%)
[04/06] Translating to English... (55%)
[05/06] Synthesizing English speech... (75%)
[06/06] Rendering dubbed video... (95%)

Completed.
Detected language: hi
Source duration:   522.3s
Processing time:   184.2s
Output:            data/output/my_video_a1b2c3d4e5f6_dubbed.mp4
```

## Web API

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/jobs` | Create a dubbing job (`{"url": "..."}`) |
| `GET` | `/api/jobs/{id}` | Job status: stage, progress, message |
| `GET` | `/api/jobs/{id}/result` | Result metadata |
| `GET` | `/api/jobs/{id}/transcript` | Original + translated segments |
| `GET` | `/api/jobs/{id}/download` | Download the final MP4 |
| `GET` | `/api/health` | Health check |
| `WS` | `/api/ws/jobs/{id}` | Live progress stream |

## Configuration (`.env`)

| Variable | Default | Notes |
|---|---|---|
| `WHISPER_MODEL` | `small` | `tiny`/`base`/`small`/`medium`/`large-v3` — bigger is more accurate, slower |
| `WHISPER_DEVICE` | `auto` | `auto` probes for CUDA and falls back to CPU |
| `TRANSLATION_PROVIDER` | `web` | `web` = free `deep-translator`-backed provider, no local model download; `local` = offline NLLB-200 via `transformers` (needs the optional deps in `requirements.txt` and a model download) |
| `TTS_VOICE` | `en-US-AriaNeural` | Any `edge-tts` voice name |
| `MAX_VIDEO_DURATION` | `7200` | Seconds; download is rejected above this |
| `MAX_SPEECH_RATE_FACTOR` | `1.35` | Cap on how much a segment's speech can be sped up to fit its timing slot |
| `COOKIES_FILE` | `cookies.txt` | Optional path to a Netscape-format cookies file (exported from a browser logged into YouTube), used to get past YouTube's bot/age checks. Ignored if the file doesn't exist — most videos don't need it. **Never commit this file** — it's already in `.gitignore`. |

## Supported languages

Any language `faster-whisper` can transcribe (Whisper's ~100 languages).
The `local` translation provider currently maps a subset of common
languages (including Hindi, Bengali, German, French, Spanish, and others)
to NLLB codes — extend `LocalNLLBProvider._LANG_MAP` in
`backend/app/services/translator.py` for others. The `web` provider
auto-detects the source language and needs no mapping.

## GPU / CPU behavior

`WHISPER_DEVICE=auto` checks for `torch.cuda.is_available()` and uses
`float16` on GPU or `int8` on CPU. No GPU is required to run the assignment;
larger Whisper models are simply slower on CPU.

## Testing

```bash
cd backend
pytest
```

Covers: YouTube URL validation, filename sanitization, config loading,
the translation-provider interface, text normalization, segment timing
(speed-up cap and silence padding) logic, job manager creation/status
transitions, and the API's health/validation/404 behavior.

These are unit and API-contract tests that don't require network access,
a GPU, or real model downloads, so they run anywhere. They intentionally
do **not** cover a full real YouTube download + Whisper + edge-tts run —
that requires internet access and is exercised manually (see below).

## Example workflow / manual verification

1. `uvicorn app.main:app --app-dir backend`
2. Open the frontend, paste a YouTube URL, watch the stage indicator move
   through Download → Extract → Transcribe → Translate → Synthesize → Render.
3. Play the result inline, or `python cli/cli.py <url>` for a terminal run.
4. Check `data/output/` for the final MP4.

## Known limitations

- Dubbing fully replaces the original audio track; background music/SFX
  preservation is not implemented (the audio layer is architected so it
  could be added: isolate speech, keep background, re-mix — see
  `services/audio_timeline.py`).
- No speaker diarization: multi-speaker videos are dubbed with a single
  voice. Diarization (`pyannote.audio`) and per-speaker voices are listed
  as a stretch goal in the assignment and are not implemented here.
- Timing alignment is segment-level (from Whisper's own segment boundaries),
  not word-level, so lip-sync is approximate by design.
- The `web` translation provider depends on an external, unofficial free
  endpoint; if it's flaky or blocked in your environment, switch to
  `TRANSLATION_PROVIDER=local` (slower first run — it downloads a model —
  but fully offline afterward).
- Long videos (2+ hours) take proportionally longer, mostly in
  transcription and TTS; there's no chunked/parallel processing across
  segments in this version.

## Troubleshooting

- **`ffmpeg/ffprobe not found on PATH`** — install FFmpeg and restart your shell.
- **yt-dlp fails to download** — YouTube changes frequently; run
  `pip install -U yt-dlp` to get the latest extractor.
- **`Sign in to confirm you're not a bot`** — export cookies from a browser
  logged into YouTube (e.g. the "Get cookies.txt LOCALLY" extension) and
  save them as `cookies.txt` in the project root; the pipeline picks it up
  automatically via `COOKIES_FILE`.
- **Translation fails with "too many requests"** — the free web translation
  endpoint is rate-limited; the built-in retry/backoff usually recovers
  automatically, but on persistent failures switch to
  `TRANSLATION_PROVIDER=local`.
- **CUDA "out of memory"** — set `WHISPER_DEVICE=cpu` or a smaller `WHISPER_MODEL`.
- **edge-tts produces no audio** — check outbound network access; edge-tts
  calls a Microsoft endpoint and needs internet access.
- **Video plays with no sound in some players** — the container is
  standard MP4/AAC; try VLC if a browser player has codec issues.

## Legal note

Only run this tool on videos you own or have permission to download and
redistribute a modified (dubbed) version of. Downloading and altering
copyrighted video without permission may violate YouTube's Terms of
Service and applicable copyright law.

## Project structure

```
automated-video-dubbing/
├── backend/            FastAPI app, services, tests, Dockerfile
├── cli/cli.py           Command-line interface
├── frontend/index.html  Static dashboard (no build step)
├── scripts/             setup.sh, setup_windows.ps1
├── data/                downloads/ audio/ jobs/ output/ (gitignored)
├── .env.example
├── docker-compose.yml
└── README.md
```
