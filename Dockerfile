FROM python:3.10-slim

# Install system dependencies and download/install Google Chrome directly
RUN apt-get update && apt-get install -y wget gnupg2 curl unzip \
    && wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get install -y ./google-chrome-stable_current_amd64.deb \
    && rm google-chrome-stable_current_amd64.deb \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Render injects a PORT environment variable
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}