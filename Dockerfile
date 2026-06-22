# Basha — container image for Render (or any Docker host).
# Render reads this file automatically; you never run it yourself.
FROM python:3.11-slim

# ffmpeg is required by pydub for audio stitching / duration reading.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (better build caching).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the project and install it (so "import basha" works).
COPY . .
RUN pip install --no-cache-dir -e .

# Render provides $PORT at runtime; bind to it on all interfaces.
ENV PORT=8000
CMD uvicorn basha.main:app --app-dir src --host 0.0.0.0 --port $PORT
