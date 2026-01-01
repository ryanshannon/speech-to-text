"""
Speech-to-Text Server using Faster-Whisper

This Flask application provides a REST API for transcribing audio files
using the faster-whisper library, which is an optimized implementation
of OpenAI's Whisper model.

Endpoints:
    - GET /health: Health check endpoint
    - POST /transcribe: Transcribe audio file to text
"""

import os
import logging
import tempfile
from flask import Flask, request, jsonify
from flask_cors import CORS
from faster_whisper import WhisperModel

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Configuration from environment variables
MODEL_SIZE = os.environ.get('WHISPER_MODEL', 'base')
DEVICE = os.environ.get('WHISPER_DEVICE', 'cpu')
COMPUTE_TYPE = os.environ.get('WHISPER_COMPUTE_TYPE', 'int8')

# Global model variable (loaded once at startup)
model = None


def load_model():
    """
    Load the Whisper model into memory.
    This is done once at startup to avoid loading delays during transcription.
    """
    global model
    logger.info(f"Loading Whisper model: {MODEL_SIZE} on {DEVICE} with {COMPUTE_TYPE}")

    try:
        model = WhisperModel(
            MODEL_SIZE,
            device=DEVICE,
            compute_type=COMPUTE_TYPE
        )
        logger.info("Whisper model loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load Whisper model: {e}")
        raise


@app.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint.
    Returns the status of the server and model information.
    """
    return jsonify({
        'status': 'healthy',
        'model': MODEL_SIZE,
        'device': DEVICE,
        'compute_type': COMPUTE_TYPE
    }), 200


@app.route('/transcribe', methods=['POST'])
def transcribe():
    """
    Transcribe an audio file to text.

    Expects:
        - A file in the request with key 'audio'
        - Optional 'language' parameter (default: auto-detect)

    Returns:
        - JSON with 'text' containing the transcription
        - JSON with 'error' on failure
    """
    # Check if audio file is present in request
    if 'audio' not in request.files:
        logger.warning("No audio file provided in request")
        return jsonify({'error': 'No audio file provided'}), 400

    audio_file = request.files['audio']

    # Check if filename is empty
    if audio_file.filename == '':
        logger.warning("Empty filename provided")
        return jsonify({'error': 'Empty filename'}), 400

    # Get optional language parameter
    language = request.form.get('language', None)

    # Create a temporary file to store the uploaded audio
    temp_file = None
    try:
        # Save uploaded file to temporary location
        temp_file = tempfile.NamedTemporaryFile(
            delete=False,
            suffix='.wav'
        )
        audio_file.save(temp_file.name)
        temp_file.close()

        logger.info(f"Processing audio file: {audio_file.filename}")

        # Transcribe the audio file
        segments, info = model.transcribe(
            temp_file.name,
            language=language,
            beam_size=5,
            vad_filter=True  # Voice Activity Detection for better accuracy
        )

        # Combine all segments into a single text
        transcription = ' '.join([segment.text.strip() for segment in segments])

        logger.info(f"Transcription complete. Detected language: {info.language}")

        return jsonify({
            'text': transcription,
            'language': info.language,
            'language_probability': info.language_probability
        }), 200

    except Exception as e:
        logger.error(f"Transcription error: {e}")
        return jsonify({'error': str(e)}), 500

    finally:
        # Clean up temporary file
        if temp_file and os.path.exists(temp_file.name):
            try:
                os.unlink(temp_file.name)
            except Exception as e:
                logger.warning(f"Failed to delete temp file: {e}")


@app.route('/models', methods=['GET'])
def list_models():
    """
    List available Whisper model sizes.
    Useful for clients to know what models can be configured.
    """
    models = {
        'tiny': 'Fastest, least accurate (~1GB VRAM)',
        'base': 'Fast, good accuracy (~1GB VRAM)',
        'small': 'Balanced speed/accuracy (~2GB VRAM)',
        'medium': 'High accuracy, slower (~5GB VRAM)',
        'large-v3': 'Best accuracy, slowest (~10GB VRAM)'
    }
    return jsonify({
        'available_models': models,
        'current_model': MODEL_SIZE
    }), 200


# Error handlers
@app.errorhandler(413)
def request_entity_too_large(error):
    """Handle file too large errors."""
    return jsonify({'error': 'Audio file too large. Maximum size is 16MB.'}), 413


@app.errorhandler(500)
def internal_server_error(error):
    """Handle internal server errors."""
    logger.error(f"Internal server error: {error}")
    return jsonify({'error': 'Internal server error'}), 500


# Load model when the application starts
with app.app_context():
    load_model()


if __name__ == '__main__':
    # Run with debug mode for development
    # In production, use gunicorn: gunicorn -w 1 -b 0.0.0.0:5000 app:app
    app.run(host='0.0.0.0', port=5000, debug=False)
