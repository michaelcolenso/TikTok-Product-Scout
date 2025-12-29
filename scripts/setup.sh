#!/bin/bash

# Setup script for TikTok Product Scout

set -e

echo "Setting up TikTok Product Scout..."

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -e .

# Install Playwright browsers
echo "Installing Playwright browsers..."
playwright install chromium

# Create directories
echo "Creating data directories..."
mkdir -p data/db data/raw data/processed logs

# Copy .env.example to .env if it doesn't exist
if [ ! -f ".env" ]; then
    echo "Creating .env file from .env.example..."
    cp .env.example .env
    echo "Please edit .env and add your configuration!"
fi

echo "Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env and add your Discord webhook URL"
echo "2. Run a test scrape: python -m src.main scrape"
echo "3. Start the API: python -m src.main api"
echo "4. Start the scheduler: python -m src.main scheduler"
