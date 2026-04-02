FROM python:3.10-slim

WORKDIR /app

# Install system deps for OpenCV (used by EasyOCR)
RUN apt-get update && apt-get install -y \
    libglib2.0-0 libsm6 libxext6 libxrender-dev libgl1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Pre-download EasyOCR models at build time so they're baked into the image
# This avoids re-downloading on every cold start at runtime
RUN python -c "import easyocr; easyocr.Reader(['en'], gpu=False)"

EXPOSE 8000

CMD uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}
