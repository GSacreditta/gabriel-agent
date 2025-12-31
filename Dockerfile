FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app
ENV PORT=8081
ENV BUILD_TIMESTAMP=2025-08-03T03:15:00Z

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    libgtk-3-0 \
    curl \
    wget \
    ghostscript \
    poppler-utils \
    tesseract-ocr \
    libtesseract-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies including FAISS
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir faiss-cpu

# Copy application code (excluding .env file for cloud deployments)
COPY app/ ./app/
COPY enhanced_main.py ./
COPY minimal_main.py ./
COPY requirements.txt ./
# Remove .env file if it exists (cloud deployments should use environment variables)
RUN rm -f /app/.env

# Create necessary directories
RUN mkdir -p /app/faiss_db \
    /app/temp \
    /app/logs \
    /app/config/credentials \
    /app/test_documents

# Set proper permissions
RUN chmod -R 755 /app && \
    chmod -R 777 /app/faiss_db && \
    chmod -R 777 /app/temp && \
    chmod -R 777 /app/logs

# Add volume mount for FAISS persistence
VOLUME ["/app/faiss_db"]

# Expose port
EXPOSE $PORT

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:$PORT/health || exit 1

# Run with full Gabriel Agent system
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8081", "--log-level", "info"] 