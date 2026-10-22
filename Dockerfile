# Python 3.11 slim base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies (including Tesseract OCR engine)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libtesseract-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend application, training modules, and ML models
COPY backend/ /app/backend/
COPY training/ /app/training/
COPY models/ /app/models/

# Expose FastAPI port
EXPOSE 8000

# Set environment defaults
ENV HOST=0.0.0.0
ENV PORT=8000
ENV DATABASE_URL=sqlite:////app/data/spam_detection.db

# Ensure persistent database volume mount point
VOLUME ["/app/data"]

# Run FastAPI backend via Uvicorn
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]