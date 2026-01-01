"""
Test Script for Speech-to-Text API

This script verifies that the Docker server is running and responding correctly.
It tests both the health endpoint and the transcription endpoint with a sample audio.

Usage:
    python test_api.py [--url URL]

Options:
    --url URL    Server URL (default: http://localhost:5000)
"""

import sys
import argparse
import wave
import struct
import math
import tempfile
import os

try:
    import requests
except ImportError:
    print("ERROR: 'requests' library not installed.")
    print("Install with: pip install requests")
    sys.exit(1)


def generate_test_tone(filename: str, duration: float = 1.0, frequency: float = 440.0):
    """
    Generate a simple sine wave audio file for testing.

    Args:
        filename: Output WAV file path
        duration: Duration in seconds
        frequency: Tone frequency in Hz
    """
    sample_rate = 16000
    num_samples = int(sample_rate * duration)

    with wave.open(filename, 'w') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)

        for i in range(num_samples):
            # Generate sine wave
            value = int(32767 * 0.3 * math.sin(2 * math.pi * frequency * i / sample_rate))
            wav_file.writeframes(struct.pack('<h', value))


def test_health(base_url: str) -> bool:
    """Test the health check endpoint."""
    print("\n1. Testing health endpoint...")
    try:
        response = requests.get(f"{base_url}/health", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"   Status: {data.get('status')}")
            print(f"   Model: {data.get('model')}")
            print(f"   Device: {data.get('device')}")
            print(f"   Compute Type: {data.get('compute_type')}")
            print("   [PASS] Health check passed!")
            return True
        else:
            print(f"   [FAIL] Unexpected status code: {response.status_code}")
            return False
    except requests.ConnectionError:
        print("   [FAIL] Cannot connect to server")
        print("   Make sure Docker container is running: docker-compose up -d")
        return False
    except Exception as e:
        print(f"   [FAIL] Error: {e}")
        return False


def test_models_endpoint(base_url: str) -> bool:
    """Test the models listing endpoint."""
    print("\n2. Testing models endpoint...")
    try:
        response = requests.get(f"{base_url}/models", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"   Current model: {data.get('current_model')}")
            print("   Available models:")
            for model, desc in data.get('available_models', {}).items():
                print(f"     - {model}: {desc}")
            print("   [PASS] Models endpoint passed!")
            return True
        else:
            print(f"   [FAIL] Unexpected status code: {response.status_code}")
            return False
    except Exception as e:
        print(f"   [FAIL] Error: {e}")
        return False


def test_transcribe_tone(base_url: str) -> bool:
    """
    Test transcription with a generated tone.
    Note: A pure tone won't produce meaningful text, but tests the endpoint.
    """
    print("\n3. Testing transcription endpoint (with test tone)...")
    print("   Note: Pure tones don't produce text; this tests API functionality.")

    temp_file = None
    try:
        # Generate test audio
        temp_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
        temp_file.close()
        generate_test_tone(temp_file.name)

        # Send to API
        with open(temp_file.name, 'rb') as audio_file:
            files = {'audio': ('test.wav', audio_file, 'audio/wav')}
            response = requests.post(
                f"{base_url}/transcribe",
                files=files,
                timeout=60
            )

        if response.status_code == 200:
            data = response.json()
            text = data.get('text', '').strip()
            lang = data.get('language', 'unknown')
            print(f"   Detected language: {lang}")
            print(f"   Transcription: '{text}' (empty is expected for tone)")
            print("   [PASS] Transcription endpoint working!")
            return True
        else:
            error = response.json().get('error', 'Unknown error')
            print(f"   [FAIL] Error: {error}")
            return False

    except Exception as e:
        print(f"   [FAIL] Error: {e}")
        return False

    finally:
        if temp_file and os.path.exists(temp_file.name):
            os.unlink(temp_file.name)


def main():
    parser = argparse.ArgumentParser(
        description='Test the Speech-to-Text API'
    )
    parser.add_argument(
        '--url',
        default='http://localhost:5000',
        help='Server URL (default: http://localhost:5000)'
    )
    args = parser.parse_args()

    print("=" * 50)
    print("  Speech-to-Text API Test Suite")
    print("=" * 50)
    print(f"\nServer URL: {args.url}")

    results = []

    # Run tests
    results.append(("Health Check", test_health(args.url)))

    # Only continue if health check passes
    if results[0][1]:
        results.append(("Models Endpoint", test_models_endpoint(args.url)))
        results.append(("Transcription", test_transcribe_tone(args.url)))

    # Summary
    print("\n" + "=" * 50)
    print("  Test Summary")
    print("=" * 50)

    all_passed = True
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  {name}: [{status}]")
        if not passed:
            all_passed = False

    print()
    if all_passed:
        print("All tests passed! The server is ready to use.")
        return 0
    else:
        print("Some tests failed. Please check the server logs.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
