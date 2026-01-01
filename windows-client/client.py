"""
Windows Push-to-Talk Speech-to-Text Client

This application runs in the background with a system tray icon. It captures
audio while a hotkey is pressed, sends it to a local Docker container running
Whisper for transcription, and copies the result to the clipboard.

Usage:
    1. Start the Docker container (docker-compose up)
    2. Run this script: python client.py
    3. The app will appear as an icon in the system tray
    4. Hold the hotkey (default: F13) and speak
    5. Release the hotkey to transcribe
    6. Transcription is automatically copied to clipboard and pasted
    7. Right-click the tray icon to exit

System Tray Icon Colors:
    - Gray: Idle/disconnected
    - Green: Ready (connected to server)
    - Red: Recording
    - Blue: Processing transcription

Requirements:
    - Python 3.8+
    - PyAudio, keyboard, requests, pyperclip, pystray, Pillow
    - Docker container running on localhost:5000
"""

import os
import sys
import json
import wave
import tempfile
import threading
import logging
import time
from pathlib import Path

import pyaudio
import keyboard
import requests
import pyperclip
import pystray
from PIL import Image, ImageDraw

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Config:
    """Configuration manager for the client."""

    DEFAULT_CONFIG = {
        "hotkey": "ctrl+shift+space",
        "api_url": "http://localhost:5000",
        "audio": {
            "sample_rate": 16000,
            "channels": 1,
            "chunk_size": 1024,
            "format": "int16"
        },
        "language": None,  # Auto-detect
        "copy_to_clipboard": True,
        "show_notifications": True
    }

    def __init__(self, config_path: str = None):
        """Load configuration from file or use defaults."""
        self.config_path = config_path or self._find_config_file()
        self.config = self._load_config()

    def _find_config_file(self) -> str:
        """Find config file in common locations."""
        locations = [
            Path(__file__).parent / "config.json",
            Path.home() / ".speech-to-text" / "config.json",
            Path("config.json")
        ]
        for loc in locations:
            if loc.exists():
                return str(loc)
        return str(locations[0])  # Default location

    def _load_config(self) -> dict:
        """Load config from file or create with defaults."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    user_config = json.load(f)
                # Merge with defaults
                config = self.DEFAULT_CONFIG.copy()
                config.update(user_config)
                if 'audio' in user_config:
                    config['audio'] = {**self.DEFAULT_CONFIG['audio'], **user_config['audio']}
                logger.info(f"Loaded config from: {self.config_path}")
                return config
            except json.JSONDecodeError as e:
                logger.error(f"Invalid config file: {e}")
                return self.DEFAULT_CONFIG.copy()
        else:
            logger.info("Using default configuration")
            return self.DEFAULT_CONFIG.copy()

    def save(self):
        """Save current config to file."""
        os.makedirs(os.path.dirname(self.config_path) or '.', exist_ok=True)
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=2)
        logger.info(f"Saved config to: {self.config_path}")

    def __getitem__(self, key):
        return self.config[key]

    def get(self, key, default=None):
        return self.config.get(key, default)


class AudioRecorder:
    """Handles audio recording using PyAudio."""

    # Map format strings to PyAudio constants
    FORMAT_MAP = {
        "int16": pyaudio.paInt16,
        "int32": pyaudio.paInt32,
        "float32": pyaudio.paFloat32
    }

    def __init__(self, config: Config):
        """Initialize the audio recorder."""
        self.config = config
        self.audio = pyaudio.PyAudio()
        self.stream = None
        self.frames = []
        self.is_recording = False
        self.lock = threading.Lock()

        # Audio settings
        self.sample_rate = config['audio']['sample_rate']
        self.channels = config['audio']['channels']
        self.chunk_size = config['audio']['chunk_size']
        self.format = self.FORMAT_MAP.get(
            config['audio']['format'],
            pyaudio.paInt16
        )

    def start_recording(self):
        """Start recording audio from the microphone."""
        with self.lock:
            if self.is_recording:
                return

            self.frames = []
            self.is_recording = True

            try:
                self.stream = self.audio.open(
                    format=self.format,
                    channels=self.channels,
                    rate=self.sample_rate,
                    input=True,
                    frames_per_buffer=self.chunk_size,
                    stream_callback=self._audio_callback
                )
                self.stream.start_stream()
                logger.debug("Recording started")
            except Exception as e:
                logger.error(f"Failed to start recording: {e}")
                self.is_recording = False
                raise

    def _audio_callback(self, in_data, frame_count, time_info, status):
        """Callback for audio stream - collects audio frames."""
        if self.is_recording:
            self.frames.append(in_data)
        return (in_data, pyaudio.paContinue)

    def stop_recording(self) -> bytes:
        """Stop recording and return the audio data."""
        with self.lock:
            if not self.is_recording:
                return b''

            self.is_recording = False

            if self.stream:
                try:
                    self.stream.stop_stream()
                    self.stream.close()
                except Exception as e:
                    logger.warning(f"Error stopping stream: {e}")
                self.stream = None

            audio_data = b''.join(self.frames)
            self.frames = []
            logger.debug(f"Recording stopped. Captured {len(audio_data)} bytes")
            return audio_data

    def save_to_file(self, audio_data: bytes, filepath: str):
        """Save audio data to a WAV file."""
        with wave.open(filepath, 'wb') as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(self.audio.get_sample_size(self.format))
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio_data)

    def cleanup(self):
        """Clean up PyAudio resources."""
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except:
                pass
        self.audio.terminate()


class TranscriptionClient:
    """Handles communication with the speech-to-text server."""

    def __init__(self, config: Config):
        """Initialize the transcription client."""
        self.config = config
        self.api_url = config['api_url']
        self.session = requests.Session()

    def check_server(self) -> bool:
        """Check if the server is available."""
        try:
            response = self.session.get(
                f"{self.api_url}/health",
                timeout=5
            )
            return response.status_code == 200
        except requests.RequestException:
            return False

    def transcribe(self, audio_filepath: str) -> dict:
        """
        Send audio file to server for transcription.

        Args:
            audio_filepath: Path to the audio file

        Returns:
            dict with 'text' on success, or 'error' on failure
        """
        try:
            with open(audio_filepath, 'rb') as audio_file:
                files = {'audio': ('audio.wav', audio_file, 'audio/wav')}
                data = {}

                # Add language if specified
                if self.config.get('language'):
                    data['language'] = self.config['language']

                response = self.session.post(
                    f"{self.api_url}/transcribe",
                    files=files,
                    data=data,
                    timeout=60  # Allow up to 60 seconds for transcription
                )

                if response.status_code == 200:
                    return response.json()
                else:
                    error_msg = response.json().get('error', 'Unknown error')
                    return {'error': error_msg}

        except requests.Timeout:
            return {'error': 'Server timeout - transcription took too long'}
        except requests.ConnectionError:
            return {'error': 'Cannot connect to server. Is Docker running?'}
        except Exception as e:
            return {'error': str(e)}


class SystrayManager:
    """Manages the system tray icon and menu."""

    # Status colors
    COLOR_IDLE = (100, 100, 100)       # Gray - idle
    COLOR_READY = (50, 150, 50)        # Green - connected
    COLOR_RECORDING = (200, 50, 50)    # Red - recording
    COLOR_PROCESSING = (50, 100, 200)  # Blue - processing

    def __init__(self, app):
        """Initialize the systray manager."""
        self.app = app
        self.icon = None
        self.current_status = "idle"
        self._create_icon()

    def _create_image(self, color):
        """Create a simple icon image with the given color."""
        # Try to load the custom icon file first
        icon_path = Path(__file__).parent / "speech2textV3.ico"
        if icon_path.exists():
            try:
                img = Image.open(icon_path)
                # Resize to standard systray size
                img = img.resize((64, 64), Image.Resampling.LANCZOS)
                return img
            except Exception:
                pass

        # Fallback: create a simple colored circle icon
        size = 64
        image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        # Draw a microphone-like shape
        # Outer circle
        margin = 4
        draw.ellipse([margin, margin, size - margin, size - margin],
                     fill=color, outline=(255, 255, 255))

        # Inner microphone shape
        mic_color = (255, 255, 255)
        center_x = size // 2
        # Mic body
        draw.rounded_rectangle([center_x - 8, 12, center_x + 8, 36],
                               radius=8, fill=mic_color)
        # Mic stand arc
        draw.arc([center_x - 14, 20, center_x + 14, 48],
                 start=0, end=180, fill=mic_color, width=3)
        # Mic stand
        draw.line([center_x, 48, center_x, 56], fill=mic_color, width=3)
        draw.line([center_x - 10, 56, center_x + 10, 56], fill=mic_color, width=3)

        return image

    def _create_icon(self):
        """Create the system tray icon."""
        menu = pystray.Menu(
            pystray.MenuItem(
                "Speech-to-Text",
                None,
                enabled=False
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                lambda item: f"Status: {self._get_status_text()}",
                None,
                enabled=False
            ),
            pystray.MenuItem(
                lambda item: f"Hotkey: {self.app.config['hotkey'].upper()}",
                None,
                enabled=False
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Exit",
                self._on_exit
            )
        )

        self.icon = pystray.Icon(
            "speech-to-text",
            self._create_image(self.COLOR_IDLE),
            "Speech-to-Text (Starting...)",
            menu
        )

    def _get_status_text(self):
        """Get human-readable status text."""
        status_map = {
            "idle": "Idle",
            "ready": "Ready",
            "recording": "Recording...",
            "processing": "Processing..."
        }
        return status_map.get(self.current_status, "Unknown")

    def _on_exit(self, icon, item):
        """Handle exit menu item."""
        logger.info("Exit requested from systray")
        self.app.running = False
        self.stop()

    def set_status(self, status):
        """Update the icon status and appearance."""
        self.current_status = status

        color_map = {
            "idle": self.COLOR_IDLE,
            "ready": self.COLOR_READY,
            "recording": self.COLOR_RECORDING,
            "processing": self.COLOR_PROCESSING
        }

        color = color_map.get(status, self.COLOR_IDLE)

        # Update icon image
        if self.icon:
            self.icon.icon = self._create_image(color)
            # Update tooltip
            tooltip = f"Speech-to-Text - {self._get_status_text()}"
            self.icon.title = tooltip

    def run(self):
        """Run the systray icon (blocking)."""
        if self.icon:
            self.icon.run()

    def stop(self):
        """Stop the systray icon."""
        if self.icon:
            self.icon.stop()


class PushToTalkApp:
    """Main application class for push-to-talk functionality."""

    def __init__(self):
        """Initialize the application."""
        logger.info("=" * 50)
        logger.info("  Speech-to-Text Push-to-Talk Client")
        logger.info("=" * 50)

        # Load configuration
        self.config = Config()

        # Initialize components
        self.recorder = AudioRecorder(self.config)
        self.client = TranscriptionClient(self.config)

        # State
        self.is_pressed = False
        self.running = True

        # Initialize systray
        self.systray = SystrayManager(self)

    def check_server_connection(self) -> bool:
        """Verify server is running."""
        logger.info("Checking server connection...")
        if self.client.check_server():
            logger.info("Server connection OK")
            self.systray.set_status("ready")
            return True
        else:
            logger.error("Cannot connect to speech-to-text server!")
            logger.error("Make sure Docker container is running: docker-compose up -d")
            logger.error(f"Expected server at: {self.config['api_url']}")
            self.systray.set_status("idle")
            return False

    def on_hotkey_press(self):
        """Called when hotkey is pressed - start recording."""
        if not self.is_pressed:
            self.is_pressed = True
            logger.info("Recording started - speak now...")
            self.systray.set_status("recording")
            try:
                self.recorder.start_recording()
            except Exception as e:
                logger.error(f"Error starting recording: {e}")
                self.is_pressed = False
                self.systray.set_status("ready")

    def on_hotkey_release(self):
        """Called when hotkey is released - stop recording and transcribe."""
        if self.is_pressed:
            self.is_pressed = False
            logger.info("Recording stopped")

            # Stop recording and get audio data
            audio_data = self.recorder.stop_recording()

            if len(audio_data) < 1000:  # Too short
                logger.warning("Recording too short, ignoring")
                self.systray.set_status("ready")
                return

            # Save to temporary file
            temp_file = None
            try:
                temp_file = tempfile.NamedTemporaryFile(
                    suffix='.wav',
                    delete=False
                )
                temp_file.close()
                self.recorder.save_to_file(audio_data, temp_file.name)

                # Send for transcription
                logger.info("Processing transcription...")
                self.systray.set_status("processing")
                result = self.client.transcribe(temp_file.name)

                if 'error' in result:
                    logger.error(f"Transcription error: {result['error']}")
                else:
                    text = result.get('text', '').strip()

                    if text:
                        logger.info(f"Transcription: {text}")

                        # Copy to clipboard and paste if enabled
                        if self.config.get('copy_to_clipboard', True):
                            try:
                                pyperclip.copy(text)
                                logger.info("Text copied to clipboard")
                                # Small delay to ensure clipboard is ready
                                time.sleep(0.05)
                                # Paste into current cursor position
                                keyboard.send('ctrl+v')
                                logger.info("Text pasted")
                            except Exception as e:
                                logger.warning(f"Could not copy/paste: {e}")
                    else:
                        logger.warning("No speech detected")

                    # Show detected language
                    if 'language' in result:
                        logger.debug(f"Detected language: {result['language']}")

            except Exception as e:
                logger.error(f"Transcription failed: {e}")

            finally:
                # Clean up temp file
                if temp_file and os.path.exists(temp_file.name):
                    try:
                        os.unlink(temp_file.name)
                    except:
                        pass
                self.systray.set_status("ready")

    def _hotkey_loop(self):
        """Background thread for hotkey detection."""
        hotkey = self.config['hotkey']

        # Register hotkey handlers
        try:
            keyboard.on_press_key(
                hotkey.split('+')[-1],  # Get the main key
                lambda e: self._check_hotkey_press(),
                suppress=False
            )
            keyboard.on_release_key(
                hotkey.split('+')[-1],
                lambda e: self._check_hotkey_release(),
                suppress=False
            )
        except Exception as e:
            # Fallback: use keyboard.add_hotkey for the full combination
            logger.debug(f"Using fallback hotkey method: {e}")
            keyboard.add_hotkey(
                hotkey,
                self.on_hotkey_press,
                suppress=False,
                trigger_on_release=False
            )

        # Poll for hotkey state
        while self.running:
            try:
                if keyboard.is_pressed(hotkey):
                    if not self.is_pressed:
                        self.on_hotkey_press()
                else:
                    if self.is_pressed:
                        self.on_hotkey_release()
                time.sleep(0.01)  # Small delay to reduce CPU usage
            except Exception as e:
                logger.debug(f"Hotkey check error: {e}")
                time.sleep(0.1)

    def run(self):
        """Main application loop."""
        # Check server connection
        if not self.check_server_connection():
            logger.warning("Server not available - will retry when hotkey is pressed")

        hotkey = self.config['hotkey']
        logger.info(f"Hotkey: {hotkey.upper()}")
        logger.info("Hold the hotkey and speak, then release to transcribe.")
        logger.info("Right-click the system tray icon to exit.")

        # Start hotkey listener in background thread
        hotkey_thread = threading.Thread(target=self._hotkey_loop, daemon=True)
        hotkey_thread.start()

        # Run systray in main thread (blocking)
        try:
            self.systray.run()
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        finally:
            self.cleanup()

        return 0

    def _check_hotkey_press(self):
        """Check if full hotkey combination is pressed."""
        hotkey = self.config['hotkey']
        if keyboard.is_pressed(hotkey):
            self.on_hotkey_press()

    def _check_hotkey_release(self):
        """Check if hotkey is released."""
        if self.is_pressed:
            self.on_hotkey_release()

    def cleanup(self):
        """Clean up resources."""
        self.running = False
        self.recorder.cleanup()
        keyboard.unhook_all()
        logger.info("Goodbye!")


def main():
    """Entry point."""
    # Check for admin privileges (needed for keyboard library on Windows)
    if sys.platform == 'win32':
        try:
            import ctypes
            if not ctypes.windll.shell32.IsUserAnAdmin():
                logger.warning("For best hotkey support, run as Administrator")
        except:
            pass

    app = PushToTalkApp()
    sys.exit(app.run())


if __name__ == '__main__':
    main()
