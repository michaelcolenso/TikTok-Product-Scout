#!/bin/bash

# Run a test scrape

set -e

echo "Running test scrape..."

source venv/bin/activate

python -m src.main scrape

echo "Test scrape complete!"
echo "Check data/db/products.db for results"
