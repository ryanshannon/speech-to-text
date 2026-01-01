# Speech-to-Text Server Dockerfile
# Uses faster-whisper for efficient speech recognition

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies required for audio processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app.py .

# Create a non-root user for security
RUN useradd -m -u 1000 whisper && \
    chown -R whisper:whisper /app

# Create cache directory for Whisper models
RUN mkdir -p /home/whisper/.cache && \
    chown -R whisper:whisper /home/whisper/.cache

USER whisper

# Environment variables (can be overridden at runtime)
ENV WHISPER_MODEL=base
ENV WHISPER_DEVICE=cpu
ENV WHISPER_COMPUTE_TYPE=int8
ENV PYTHONUNBUFFERED=1

# Expose the API port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')" || exit 1

# Run with gunicorn for production
# Using 1 worker because the model is memory-intensive
# Timeout set high for first request (model loading)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--timeout", "120", "app:app"]
