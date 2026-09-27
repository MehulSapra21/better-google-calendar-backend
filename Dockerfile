FROM python:3.10-slim

# Install system dependencies, Google Chrome, and Xvfb
RUN apt-get update && apt-get install -y wget gnupg2 curl unzip xvfb \
    && wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get install -y ./google-chrome-stable_current_amd64.deb \
    && rm google-chrome-stable_current_amd64.deb \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Launch the app inside a virtual 1920x1080 display
CMD xvfb-run --server-args="-screen 0 1920x1080x24" uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}