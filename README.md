# Local Speech-to-Text with Push-to-Talk

A fully local, privacy-focused speech-to-text system using OpenAI's Whisper model. Hold a hotkey, speak, and get instant transcriptions copied to your clipboard.

## Features

- **100% Local**: All processing happens on your machine - no cloud services, no data leaves your PC
- **Push-to-Talk**: Hold a configurable hotkey to record, release to transcribe
- **Fast**: Uses faster-whisper for optimized performance
- **Easy Setup**: Docker container handles all dependencies
- **Clipboard Integration**: Transcriptions are automatically copied to clipboard
- **Configurable**: Change hotkeys, model size, and audio settings
- **GPU Accelerated**: Optional NVIDIA CUDA support for faster transcription

## Project Structure

```
speech-to-text/
├── speech-to-text-server/     # Docker container with Whisper
│   ├── Dockerfile             # CPU version
│   ├── Dockerfile.gpu         # GPU/CUDA version
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

## GPU Acceleration (NVIDIA CUDA)

If you have an NVIDIA GPU, you can use CUDA acceleration for significantly faster transcription.

### GPU Prerequisites

1. **NVIDIA GPU** with CUDA support (GTX 1060 or better recommended)
2. **NVIDIA Drivers** installed (version 525+ recommended)
3. **NVIDIA Container Toolkit** installed

### Installing NVIDIA Container Toolkit on Windows

1. Make sure you have the latest NVIDIA drivers installed
2. In Docker Desktop, go to Settings → Resources → WSL Integration
3. Enable integration with your WSL2 distro
4. Install the NVIDIA Container Toolkit in WSL2:

```bash
# Run these commands in WSL2 (Ubuntu)
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker
```

5. Verify GPU is accessible:
```powershell
docker run --rm --gpus all nvidia/cuda:12.1.1-base-ubuntu22.04 nvidia-smi
```

### Running with GPU

Build and start the GPU version:

```powershell
docker-compose --profile gpu up -d
```

Stop the GPU version:

```powershell
docker-compose --profile gpu down
```

Rebuild GPU image:

```powershell
docker-compose --profile gpu build --no-cache
```

### GPU vs CPU Comparison

| Aspect | CPU | GPU |
|--------|-----|-----|
| `base` model | ~2-4 sec | ~0.3-0.5 sec |
| `small` model | ~5-10 sec | ~0.5-1 sec |
| `medium` model | ~15-30 sec | ~1-2 sec |
| `large-v3` model | ~30-60 sec | ~2-4 sec |
| Memory usage | System RAM | GPU VRAM |
| First startup | ~30 sec | ~60 sec |

*Times are approximate for a 10-second audio clip*

### Switching Between CPU and GPU

Only one version can run at a time (they use the same port):

```powershell
# Stop CPU version, start GPU version
docker-compose down
docker-compose --profile gpu up -d

# Stop GPU version, start CPU version
docker-compose --profile gpu down
docker-compose up -d
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

1. **Use GPU acceleration** if you have an NVIDIA GPU - see GPU section above
2. Try a smaller model - `tiny` or `base` are fastest
3. Ensure Docker has enough RAM (4GB+ recommended)
4. Check CPU usage - close other heavy applications
5. Keep recordings short - shorter audio processes faster

### Container keeps restarting

Check logs for errors:
```powershell
docker-compose logs speech-to-text
```

Common issues:
- Not enough memory: Increase Docker memory limit in Docker Desktop settings
- Port conflict: Another application using port 5000

### GPU not detected / CUDA errors

1. Verify NVIDIA drivers are installed: `nvidia-smi` in PowerShell
2. Verify Docker can see GPU:
   ```powershell
   docker run --rm --gpus all nvidia/cuda:12.1.1-base-ubuntu22.04 nvidia-smi
   ```
3. Check NVIDIA Container Toolkit is installed in WSL2
4. Restart Docker Desktop after installing toolkit
5. Check GPU memory - close other GPU-intensive applications

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
