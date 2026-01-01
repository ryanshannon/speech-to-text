"""
Windows Push-to-Talk Speech-to-Text Client

This application captures audio while a hotkey is pressed, sends it to a
local Docker container running Whisper for transcription, and copies the
result to the clipboard.

Usage:
    1. Start the Docker container (docker-compose up)
    2. Run this script: python client.py
    3. Hold the hotkey (default: Ctrl+Shift+Space) and speak
    4. Release the hotkey to transcribe
    5. Transcription is automatically copied to clipboard

Requirements:
    - Python 3.8+
    - PyAudio, keyboard, requests, pyperclip
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


class PushToTalkApp:
    """Main application class for push-to-talk functionality."""

    def __init__(self):
        """Initialize the application."""
        print("\n" + "=" * 50)
        print("  Speech-to-Text Push-to-Talk Client")
        print("=" * 50 + "\n")

        # Load configuration
        self.config = Config()

        # Initialize components
        self.recorder = AudioRecorder(self.config)
        self.client = TranscriptionClient(self.config)

        # State
        self.is_pressed = False
        self.running = True

    def check_server_connection(self) -> bool:
        """Verify server is running."""
        print("Checking server connection...", end=" ")
        if self.client.check_server():
            print("OK")
            return True
        else:
            print("FAILED")
            print("\nERROR: Cannot connect to speech-to-text server!")
            print("Make sure Docker container is running:")
            print("  docker-compose up -d")
            print(f"\nExpected server at: {self.config['api_url']}")
            return False

    def on_hotkey_press(self):
        """Called when hotkey is pressed - start recording."""
        if not self.is_pressed:
            self.is_pressed = True
            print("\n[RECORDING] Speak now...", end="", flush=True)
            try:
                self.recorder.start_recording()
            except Exception as e:
                print(f"\nError starting recording: {e}")
                self.is_pressed = False

    def on_hotkey_release(self):
        """Called when hotkey is released - stop recording and transcribe."""
        if self.is_pressed:
            self.is_pressed = False
            print(" Done!")

            # Stop recording and get audio data
            audio_data = self.recorder.stop_recording()

            if len(audio_data) < 1000:  # Too short
                print("[WARNING] Recording too short, ignoring")
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
                print("[PROCESSING] Transcribing...", end=" ", flush=True)
                result = self.client.transcribe(temp_file.name)

                if 'error' in result:
                    print("FAILED")
                    print(f"[ERROR] {result['error']}")
                else:
                    print("Done!")
                    text = result.get('text', '').strip()

                    if text:
                        print(f"\n[TRANSCRIPTION]\n{text}\n")

                        # Copy to clipboard if enabled
                        if self.config.get('copy_to_clipboard', True):
                            try:
                                pyperclip.copy(text)
                                print("[CLIPBOARD] Text copied!")
                            except Exception as e:
                                print(f"[WARNING] Could not copy to clipboard: {e}")
                    else:
                        print("[WARNING] No speech detected")

                    # Show detected language
                    if 'language' in result:
                        logger.debug(f"Detected language: {result['language']}")

            except Exception as e:
                print(f"\n[ERROR] Transcription failed: {e}")

            finally:
                # Clean up temp file
                if temp_file and os.path.exists(temp_file.name):
                    try:
                        os.unlink(temp_file.name)
                    except:
                        pass

    def run(self):
        """Main application loop."""
        # Check server connection
        if not self.check_server_connection():
            return 1

        hotkey = self.config['hotkey']
        print(f"\nHotkey: {hotkey.upper()}")
        print("Hold the hotkey and speak, then release to transcribe.")
        print("Press Ctrl+C to exit.\n")
        print("-" * 50)

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

        # Alternative approach: poll for hotkey state
        try:
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

        except KeyboardInterrupt:
            print("\n\nShutting down...")

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
        print("Goodbye!")


def main():
    """Entry point."""
    # Check for admin privileges (needed for keyboard library on Windows)
    if sys.platform == 'win32':
        try:
            import ctypes
            if not ctypes.windll.shell32.IsUserAnAdmin():
                print("NOTE: For best hotkey support, run as Administrator")
                print("      (Right-click -> Run as administrator)\n")
        except:
            pass

    app = PushToTalkApp()
    sys.exit(app.run())


if __name__ == '__main__':
    main()
