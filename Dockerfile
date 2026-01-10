# Use official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
# PYTHONDONTWRITEBYTECODE PREVENTS Python from writing pyc files to disc
# PYTHONUNBUFFERED ensures stdout/stderr are flushed immediately (vital for logs)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# Set work directory
WORKDIR /app

# Install system dependencies
# ffmpeg is REQUIRED for audio processing in LiveKit/Piper
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Create a volume for persistent data (like logs, config updates)
VOLUME ["/app/data"]

# Default command (can be overridden in docker-compose)
CMD ["python", "web_server.py"]
