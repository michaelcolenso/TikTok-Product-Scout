"""Configuration management utilities"""

import os
import yaml
from pathlib import Path
from typing import Any, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """Configuration manager for the application"""

    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            # Default to config/config.yaml in project root
            project_root = Path(__file__).parent.parent.parent
            config_path = project_root / "config" / "config.yaml"

        self.config_path = Path(config_path)
        self._config = self._load_config()

    def _load_config(self) -> dict:
        """Load configuration from YAML file"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

        with open(self.config_path, "r") as f:
            return yaml.safe_load(f)

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by dot-notation key (e.g., 'database.url')"""
        keys = key.split(".")
        value = self._config

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default

        return value if value is not None else default

    def get_env(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get environment variable"""
        return os.getenv(key, default)

    @property
    def database_url(self) -> str:
        """Get database URL from env or config"""
        return self.get_env("DATABASE_URL") or self.get("database.url", "sqlite:///data/db/products.db")

    @property
    def discord_webhook_url(self) -> Optional[str]:
        """Get Discord webhook URL from env"""
        return self.get_env("DISCORD_WEBHOOK_URL")

    @property
    def log_level(self) -> str:
        """Get log level"""
        return self.get_env("LOG_LEVEL", "INFO")


# Global config instance
config = Config()
