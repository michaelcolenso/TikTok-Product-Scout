FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements
COPY pyproject.toml .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# Install Playwright and browsers
RUN pip install --no-cache-dir playwright && \
    playwright install --with-deps chromium

# Copy application code
COPY src/ src/
COPY config/ config/

# Create data directories
RUN mkdir -p data/db data/raw data/processed data/logs

# Set environment
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Expose API port
EXPOSE 8000

# Default command (can be overridden)
CMD ["python", "-m", "src", "scheduler"]
