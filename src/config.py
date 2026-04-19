"""Configuration loader for Google Classroom Notifier."""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load .env file if exists
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)


@dataclass
class Config:
    """Configuration settings."""

    credentials_file: str = "credentials.json"
    token_file: str = "config/token.json"
    check_interval_minutes: int = 15
    state_file: str = "/tmp/gcn_state.json"
    daemon_mode: bool = False
    log_level: str = "INFO"

    def validate(self) -> list[str]:
        """Validate configuration and return list of errors."""
        errors = []

        if not self.credentials_file:
            errors.append("credentials_file is required")
        elif not Path(self.credentials_file).exists():
            errors.append(f"credentials_file not found: {self.credentials_file}")

        if self.check_interval_minutes < 1:
            errors.append("check_interval_minutes must be >= 1")

        if self.log_level not in ("DEBUG", "INFO", "WARNING", "ERROR"):
            errors.append(f"invalid log_level: {self.log_level}")

        return errors


def load_config(config_path: Optional[str] = None) -> Config:
    """Load configuration from file or environment."""
    if config_path is None:
        config_path = os.environ.get("GCN_CONFIG_PATH", "config/config.json")

    config_file = Path(config_path)

    # Try to load from file
    if config_file.exists():
        with open(config_file, "r") as f:
            data = json.load(f)
    else:
        data = {}

    # Environment variables override file config
    return Config(
        credentials_file=os.environ.get("CREDENTIALS_FILE", data.get("credentials_file", "credentials.json")),
        token_file=os.environ.get("TOKEN_FILE", data.get("token_file", "config/token.json")),
        check_interval_minutes=int(os.environ.get("CHECK_INTERVAL_MINUTES", data.get("check_interval_minutes", 15))),
        state_file=os.environ.get("STATE_FILE", data.get("state_file", "/tmp/gcn_state.json")),
        daemon_mode=os.environ.get("DAEMON_MODE", "false").lower() == "true",
        log_level=os.environ.get("LOG_LEVEL", data.get("log_level", "INFO")),
    )