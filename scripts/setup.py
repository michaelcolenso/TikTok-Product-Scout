#!/usr/bin/env python3
"""Setup script for TikTok Product Scout."""

import os
import subprocess
import sys
from pathlib import Path


def main():
    """Run setup tasks."""
    print("=" * 80)
    print("TikTok Product Scout - Setup")
    print("=" * 80)

    # Check Python version
    if sys.version_info < (3, 11):
        print("Error: Python 3.11 or higher is required")
        sys.exit(1)

    print("\n✓ Python version check passed")

    # Create directories
    print("\n Creating directories...")
    dirs = [
        "data/db",
        "data/raw",
        "data/processed",
        "data/logs",
    ]

    for dir_path in dirs:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
        print(f"  ✓ Created {dir_path}")

    # Install dependencies
    print("\n📦 Installing dependencies...")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-e", "."],
            check=True,
        )
        print("  ✓ Dependencies installed")
    except subprocess.CalledProcessError:
        print("  ✗ Failed to install dependencies")
        sys.exit(1)

    # Install Playwright browsers
    print("\n🎭 Installing Playwright browsers...")
    try:
        subprocess.run(
            ["playwright", "install", "chromium"],
            check=True,
        )
        print("  ✓ Playwright browsers installed")
    except subprocess.CalledProcessError:
        print("  ⚠ Failed to install Playwright browsers (you may need to do this manually)")

    # Check for .env file
    if not os.path.exists(".env"):
        print("\n⚠ No .env file found. Creating from .env.example...")
        if os.path.exists(".env.example"):
            subprocess.run(["cp", ".env.example", ".env"])
            print("  ✓ Created .env file - please edit it with your configuration")
        else:
            print("  ✗ .env.example not found")
    else:
        print("\n✓ .env file exists")

    # Initialize database
    print("\n🗄 Initializing database...")
    try:
        # Import here to ensure dependencies are installed
        from src.storage.database import Database

        db = Database()
        print("  ✓ Database initialized")
    except Exception as e:
        print(f"  ✗ Failed to initialize database: {e}")
        sys.exit(1)

    print("\n" + "=" * 80)
    print("✅ Setup completed successfully!")
    print("=" * 80)
    print("\nNext steps:")
    print("1. Edit .env file with your API keys and configuration")
    print("2. Run 'python -m src scheduler' to start the scheduler")
    print("3. Run 'python -m src api' to start the API server")
    print("\nFor more information, see README.md")


if __name__ == "__main__":
    main()
