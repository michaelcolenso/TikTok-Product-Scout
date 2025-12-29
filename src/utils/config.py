"""Configuration management for TikTok Product Scout."""

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class DatabaseConfig(BaseModel):
    """Database configuration."""

    url: str = "sqlite:///data/db/products.db"
    echo: bool = False


class ScrapingConfig(BaseModel):
    """Scraping configuration."""

    rate_limit_delay: float = 2.0
    max_retries: int = 3
    timeout: int = 30
    agents: Dict[str, Any] = Field(default_factory=dict)


class ScoringConfig(BaseModel):
    """Scoring configuration."""

    weights: Dict[str, float] = Field(
        default_factory=lambda: {"velocity": 0.35, "margin": 0.30, "saturation": 0.35}
    )
    margin: Dict[str, float] = Field(default_factory=dict)
    velocity: Dict[str, float] = Field(default_factory=dict)
    saturation: Dict[str, Any] = Field(default_factory=dict)


class AlertThresholds(BaseModel):
    """Alert threshold configuration."""

    min_composite_score: float = 70.0
    min_velocity_score: float = 60.0
    min_margin_score: float = 50.0
    min_saturation_score: float = 60.0
    velocity_spike_threshold: float = 100.0
    new_product_min_score: float = 65.0
    min_hours_between_alerts: int = 24


class AlertsConfig(BaseModel):
    """Alerts configuration."""

    thresholds: AlertThresholds = Field(default_factory=AlertThresholds)
    discord: Dict[str, Any] = Field(default_factory=dict)
    email: Dict[str, Any] = Field(default_factory=dict)
    webhook: Dict[str, Any] = Field(default_factory=dict)


class ScheduleConfig(BaseModel):
    """Scheduling configuration."""

    tiktok_creative_center_hours: int = 4
    tiktok_shop_hours: int = 6
    aliexpress_hours: int = 12
    amazon_hours: int = 8
    scoring_hours: int = 2
    alert_check_minutes: int = 30
    cleanup_days: int = 30


class APIConfig(BaseModel):
    """API configuration."""

    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: str = "INFO"
    format: str = "json"
    file: str = "data/logs/scout.log"


class AntiDetectionConfig(BaseModel):
    """Anti-detection configuration."""

    use_proxies: bool = False
    rotate_user_agents: bool = True
    random_delays: bool = True
    min_delay: float = 1.0
    max_delay: float = 5.0


class Config(BaseModel):
    """Main configuration model."""

    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    scraping: ScrapingConfig = Field(default_factory=ScrapingConfig)
    scoring: ScoringConfig = Field(default_factory=ScoringConfig)
    alerts: AlertsConfig = Field(default_factory=AlertsConfig)
    schedule: ScheduleConfig = Field(default_factory=ScheduleConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    anti_detection: AntiDetectionConfig = Field(default_factory=AntiDetectionConfig)


class Settings(BaseSettings):
    """Environment-based settings."""

    # Database
    database_url: str = "sqlite:///data/db/products.db"

    # Proxy
    proxy_list: str = ""

    # Third-party APIs
    kalodata_api_key: str = ""
    fastmoss_api_key: str = ""

    # Alerting
    discord_webhook_url: str = ""
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_recipients: str = ""
    webhook_url: str = ""

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    secret_key: str = ""
    api_key: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


class ConfigManager:
    """Configuration manager for loading and merging config sources."""

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize configuration manager.

        Args:
            config_path: Path to YAML configuration file
        """
        # Load environment variables
        load_dotenv()

        # Load YAML config
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "config.yaml"

        self.config_path = config_path
        self.yaml_config = self._load_yaml()

        # Load environment settings
        self.env_settings = Settings()

        # Merge configurations
        self.config = self._merge_config()

    def _load_yaml(self) -> Dict[str, Any]:
        """Load YAML configuration file."""
        if not self.config_path.exists():
            return {}

        with open(self.config_path, "r") as f:
            return yaml.safe_load(f) or {}

    def _merge_config(self) -> Config:
        """Merge YAML config with environment variables."""
        # Start with YAML config
        merged = self.yaml_config.copy()

        # Override with environment variables where applicable
        if self.env_settings.database_url:
            merged.setdefault("database", {})["url"] = self.env_settings.database_url

        if self.env_settings.discord_webhook_url:
            merged.setdefault("alerts", {}).setdefault("discord", {})[
                "webhook_url"
            ] = self.env_settings.discord_webhook_url

        if self.env_settings.log_level:
            merged.setdefault("logging", {})["level"] = self.env_settings.log_level

        if self.env_settings.api_host:
            merged.setdefault("api", {})["host"] = self.env_settings.api_host

        if self.env_settings.api_port:
            merged.setdefault("api", {})["port"] = self.env_settings.api_port

        return Config(**merged)

    def get_proxies(self) -> list[str]:
        """Get list of proxies from environment."""
        if not self.env_settings.proxy_list:
            return []
        return [p.strip() for p in self.env_settings.proxy_list.split(",") if p.strip()]

    def get_email_recipients(self) -> list[str]:
        """Get list of email recipients."""
        if not self.env_settings.email_recipients:
            return []
        return [e.strip() for e in self.env_settings.email_recipients.split(",") if e.strip()]


# Global config instance
_config_manager: Optional[ConfigManager] = None


def get_config() -> Config:
    """Get global configuration instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager.config


def get_settings() -> Settings:
    """Get environment settings."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager.env_settings


def get_config_manager() -> ConfigManager:
    """Get configuration manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager
