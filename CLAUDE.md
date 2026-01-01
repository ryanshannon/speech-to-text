# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Local, privacy-focused speech-to-text system using OpenAI's Whisper model. Two components:
- **Server**: Docker-based Flask API running faster-whisper (CPU or GPU)
- **Client**: Windows push-to-talk application with system tray UI

## Common Commands

### Server (Docker)

```bash
# Start CPU version (default)
docker-compose up -d

# Start GPU version (requires NVIDIA Container Toolkit)
docker-compose --profile gpu up -d

# Stop
docker-compose down
# or for GPU: docker-compose --profile gpu down

# View logs
docker-compose logs -f

# Rebuild after changes
docker-compose up -d --build
```

### Client (Windows)

```bash
cd windows-client

# Build standalone executable
.\build.bat

# Run executable
.\dist\speech-to-text-client.exe
```

### Testing

```bash
# Test server API (health, models, transcription with generated tone)
python test_api.py
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    WINDOWS CLIENT                            │
│  PushToTalkApp (orchestrator)                                │
│   ├─ Config: JSON settings (~/.speech-to-text/config.json)   │
│   ├─ AudioRecorder: PyAudio streaming → WAV                  │
│   ├─ TranscriptionClient: HTTP POST to server                │
│   └─ SystrayManager: 4-state icon (gray/green/red/blue)      │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTP POST /transcribe (multipart WAV)
┌──────────────────────▼──────────────────────────────────────┐
│               DOCKER CONTAINER (Flask/Gunicorn)              │
│  ├─ GET /health - server status                              │
│  ├─ POST /transcribe - audio → text (VAD + beam search)      │
│  └─ GET /models - available Whisper models                   │
│  WhisperModel loaded once at startup (global singleton)      │
└──────────────────────────────────────────────────────────────┘
```

## Key Configuration

### Server (`docker-compose.yml` environment)
- `WHISPER_MODEL`: tiny, base, small, medium, large-v3
- `WHISPER_DEVICE`: cpu, cuda
- `WHISPER_COMPUTE_TYPE`: int8 (CPU), float16 (GPU)

### Client (`windows-client/config.json`)
- `hotkey`: Push-to-talk key (default: "F13")
- `api_url`: Server URL (default: "http://localhost:5000")
- `audio`: sample_rate, channels, chunk_size, format
- `copy_to_clipboard`: Auto-copy transcription

## Important Patterns

- **Single worker**: Server uses 1 Gunicorn worker to prevent memory exhaustion from parallel Whisper instances
- **Model caching**: Docker volume `whisper-cache` persists downloaded models (~150MB-3GB)
- **Thread safety**: Client uses Lock for audio frame mutations; hotkey runs in daemon thread
- **Config merge**: Client overlays user config on defaults, allowing partial configs
- **Timeouts**: 120s server startup (model loading), 60s transcription, 5s health check
