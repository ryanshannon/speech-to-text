# Local Speech-to-Text with Push-to-Talk

A fully local, privacy-focused speech-to-text system using OpenAI's Whisper model. Hold a hotkey, speak, and get instant transcriptions copied to your clipboard.

## Features

- **100% Local**: All processing happens on your machine - no cloud services, no data leaves your PC
- **Push-to-Talk**: Hold a configurable hotkey to record, release to transcribe
- **Fast**: Uses faster-whisper for optimized performance
- **Easy Setup**: Docker container handles all dependencies
- **Clipboard Integration**: Transcriptions are automatically copied to clipboard
- **Configurable**: Change hotkeys, model size, and audio settings

## Project Structure

```
speech-to-text/
├── speech-to-text-server/     # Docker container with Whisper
│   ├── Dockerfile
│   ├── app.py                 # Flask API server
│   └── requirements.txt
├── windows-client/            # Windows push-to-talk client
│   ├── client.py              # Main client application
│   ├── config.json            # Client configuration
│   ├── requirements.txt
│   └── start_client.bat       # Easy startup script
├── docker-compose.yml         # Container orchestration
├── test_api.py               # API test script
├── .gitignore
└── README.md
```

## Prerequisites

Before you begin, make sure you have:

1. **Windows 11** (Windows 10 should also work)
2. **Docker Desktop** installed and running
   - Download from: https://www.docker.com/products/docker-desktop
   - Enable WSL2 backend during installation
3. **Python 3.8+** installed on Windows
   - Download from: https://www.python.org/downloads/
   - **Important**: Check "Add Python to PATH" during installation
4. **Microphone** connected and working

## Installation

### Step 1: Start Docker Desktop

Make sure Docker Desktop is running. You should see the Docker icon in your system tray.

### Step 2: Build and Start the Server

Open a terminal (PowerShell or Command Prompt) and navigate to the project folder:

```powershell
cd C:\path\to\speech-to-text
```

Build and start the Docker container:

```powershell
docker-compose up -d
```

The first run will:
1. Download the base Docker image (~1GB)
2. Install dependencies
3. Download the Whisper model (~150MB for 'base')

This may take 5-10 minutes on first run. Subsequent starts are instant.

### Step 3: Verify the Server

Test that the server is running:

```powershell
python test_api.py
```

You should see all tests pass:
```
  Health Check: [PASS]
  Models Endpoint: [PASS]
  Transcription: [PASS]
```

### Step 4: Install Client Dependencies

```powershell
cd windows-client
pip install -r requirements.txt
```

**Note**: If you get errors installing PyAudio, you may need to install it separately:
```powershell
pip install pipwin
pipwin install pyaudio
```

### Step 5: Run the Client

Double-click `start_client.bat` in the `windows-client` folder, or run:

```powershell
python client.py
```

## Usage

1. **Start the server** (if not already running):
   ```powershell
   docker-compose up -d
   ```

2. **Start the client**:
   - Double-click `windows-client/start_client.bat`
   - Or run `python windows-client/client.py`

3. **Record speech**:
   - Hold **Ctrl+Shift+Space** (default hotkey)
   - Speak clearly into your microphone
   - Release the keys when done

4. **Get transcription**:
   - The text appears in the console
   - It's automatically copied to your clipboard
   - Paste anywhere with Ctrl+V

## Configuration

Edit `windows-client/config.json` to customize:

```json
{
  "hotkey": "ctrl+shift+space",
  "api_url": "http://localhost:5000",
  "audio": {
    "sample_rate": 16000,
    "channels": 1,
    "chunk_size": 1024,
    "format": "int16"
  },
  "language": null,
  "copy_to_clipboard": true
}
```

### Configuration Options

| Option | Description | Default |
|--------|-------------|---------|
| `hotkey` | Key combination to hold while speaking | `ctrl+shift+space` |
| `api_url` | Server URL | `http://localhost:5000` |
| `sample_rate` | Audio sample rate in Hz | `16000` |
| `channels` | Audio channels (1=mono) | `1` |
| `language` | Force language (e.g., "en"), or null for auto-detect | `null` |
| `copy_to_clipboard` | Auto-copy transcription to clipboard | `true` |

### Changing the Hotkey

Edit `config.json` and change the `hotkey` value. Examples:
- `"ctrl+alt+r"` - Ctrl+Alt+R
- `"f9"` - F9 key
- `"ctrl+shift+t"` - Ctrl+Shift+T

Restart the client after changing.

## Changing the Whisper Model

Edit `docker-compose.yml` and change `WHISPER_MODEL`:

```yaml
environment:
  - WHISPER_MODEL=small  # Change from 'base' to desired model
```

Available models:

| Model | Size | Speed | Accuracy | VRAM |
|-------|------|-------|----------|------|
| `tiny` | 75MB | Fastest | Basic | ~1GB |
| `base` | 150MB | Fast | Good | ~1GB |
| `small` | 500MB | Medium | Better | ~2GB |
| `medium` | 1.5GB | Slow | High | ~5GB |
| `large-v3` | 3GB | Slowest | Best | ~10GB |

After changing, rebuild the container:
```powershell
docker-compose down
docker-compose up -d --build
```

## Managing the Server

### Start server
```powershell
docker-compose up -d
```

### Stop server
```powershell
docker-compose down
```

### View logs
```powershell
docker-compose logs -f
```

### Restart server
```powershell
docker-compose restart
```

### Check status
```powershell
docker-compose ps
```

## Troubleshooting

### "Cannot connect to server"

1. Check Docker Desktop is running
2. Check the container is running: `docker-compose ps`
3. Check container logs: `docker-compose logs`
4. Verify the port: `curl http://localhost:5000/health`

### "No audio captured" or "Recording too short"

1. Check your microphone is connected
2. Check Windows sound settings - make sure the correct mic is default
3. Try speaking louder or adjusting mic volume
4. Test your mic in another application

### PyAudio installation fails

On Windows, PyAudio can be tricky to install. Try:

```powershell
pip install pipwin
pipwin install pyaudio
```

Or download a prebuilt wheel from:
https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio

### Hotkey not working

1. Try running the client as Administrator (right-click → Run as administrator)
2. Make sure no other application is using the same hotkey
3. Try a different hotkey combination in `config.json`

### Transcription is slow

1. Upgrade to a faster model isn't always better - try `tiny` or `base` first
2. Ensure Docker has enough RAM (4GB+ recommended)
3. Check CPU usage - close other heavy applications
4. If you have an NVIDIA GPU, consider using CUDA (advanced setup)

### Container keeps restarting

Check logs for errors:
```powershell
docker-compose logs speech-to-text
```

Common issues:
- Not enough memory: Increase Docker memory limit in Docker Desktop settings
- Port conflict: Another application using port 5000

## Performance Tips

1. **Use the right model**: Start with `base` for a good balance of speed and accuracy
2. **Keep recordings short**: Shorter audio = faster processing
3. **Speak clearly**: Whisper works best with clear speech
4. **Reduce background noise**: Quiet environment = better accuracy
5. **Allocate resources**: Give Docker at least 4GB RAM in Docker Desktop settings

## API Reference

The server exposes these endpoints:

### GET /health
Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "model": "base",
  "device": "cpu",
  "compute_type": "int8"
}
```

### POST /transcribe
Transcribe an audio file.

**Request:**
- Method: POST
- Content-Type: multipart/form-data
- Body: `audio` file (WAV format recommended)
- Optional: `language` parameter (e.g., "en", "es", "fr")

**Response:**
```json
{
  "text": "The transcribed text appears here",
  "language": "en",
  "language_probability": 0.98
}
```

### GET /models
List available models.

**Response:**
```json
{
  "available_models": {
    "tiny": "Fastest, least accurate",
    "base": "Fast, good accuracy",
    ...
  },
  "current_model": "base"
}
```

## License

This project is provided as-is for personal use. Whisper model is from OpenAI and subject to their license.

## Acknowledgments

- [OpenAI Whisper](https://github.com/openai/whisper) - The speech recognition model
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) - Optimized Whisper implementation
- [Flask](https://flask.palletsprojects.com/) - Web framework
- [PyAudio](https://people.csail.mit.edu/hubert/pyaudio/) - Audio capture
