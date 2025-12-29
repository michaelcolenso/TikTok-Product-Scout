FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list' \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements
COPY pyproject.toml .

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# Install Playwright browsers
RUN pip install playwright && playwright install chromium

# Copy application
COPY src/ src/
COPY config/ config/

# Create data directories
RUN mkdir -p data/db data/raw data/processed logs

# Expose API port
EXPOSE 8000

# Default command
CMD ["python", "-m", "src.main", "scheduler"]
