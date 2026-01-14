"""Configuration management for the tax agent."""

import json
import os
from pathlib import Path
from typing import Any

import keyring

APP_NAME = "tax-prep-agent"
DEFAULT_CONFIG_DIR = Path.home() / ".tax-agent"
DEFAULT_DATA_DIR = DEFAULT_CONFIG_DIR / "data"
DEFAULT_DB_PATH = DEFAULT_DATA_DIR / "tax_data.db"

KEYRING_SERVICE = "tax-prep-agent"
KEYRING_API_KEY = "anthropic-api-key"
KEYRING_AWS_ACCESS_KEY = "aws-access-key-id"
KEYRING_AWS_SECRET_KEY = "aws-secret-access-key"
KEYRING_DB_PASSWORD = "db-encryption-key"
KEYRING_GOOGLE_CREDENTIALS = "google-drive-credentials"
KEYRING_GOOGLE_CLIENT_CONFIG = "google-drive-client-config"

# Supported AI providers
AI_PROVIDER_ANTHROPIC = "anthropic"
AI_PROVIDER_AWS_BEDROCK = "aws_bedrock"


class Config:
    """Manages application configuration."""

    def __init__(self, config_dir: Path | None = None):
        self.config_dir = config_dir or DEFAULT_CONFIG_DIR
        self.config_file = self.config_dir / "config.json"
        self.data_dir = self.config_dir / "data"
        self._config: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        """Load configuration from file."""
        if self.config_file.exists():
            with open(self.config_file) as f:
                self._config = json.load(f)
        else:
            self._config = self._default_config()

    def _save(self) -> None:
        """Save configuration to file."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, "w") as f:
            json.dump(self._config, f, indent=2)

    def _default_config(self) -> dict[str, Any]:
        """Return default configuration."""
        return {
            "tax_year": 2024,
            "state": None,
            "filing_status": None,
            "ai_provider": AI_PROVIDER_ANTHROPIC,  # "anthropic" or "aws_bedrock"
            "model": "claude-sonnet-4-5",
            "aws_region": "us-east-1",
            "ocr_engine": "pytesseract",
            "auto_redact_ssn": True,
            "initialized": False,
            # Agent SDK settings
            "use_agent_sdk": False,  # Opt-in to new SDK features
            "agent_sdk_max_turns": 10,  # Maximum agentic turns
            "agent_sdk_allow_web": True,  # Allow web search/fetch tools
        }

    @property
    def is_initialized(self) -> bool:
        """Check if the application has been initialized."""
        return self._config.get("initialized", False)

    def initialize(self, password: str) -> None:
        """Initialize the application with encryption."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Store the database encryption key in the system keyring
        keyring.set_password(KEYRING_SERVICE, KEYRING_DB_PASSWORD, password)

        self._config["initialized"] = True
        self._save()

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value."""
        self._config[key] = value
        self._save()

    def get_api_key(self) -> str | None:
        """Get the Anthropic API key from environment or keyring."""
        # Check environment variable first
        env_key = os.environ.get("ANTHROPIC_API_KEY")
        if env_key:
            return env_key
        # Fall back to keyring
        return keyring.get_password(KEYRING_SERVICE, KEYRING_API_KEY)

    def set_api_key(self, api_key: str) -> None:
        """Store the Anthropic API key in the system keyring."""
        keyring.set_password(KEYRING_SERVICE, KEYRING_API_KEY, api_key)

    def get_aws_credentials(self) -> tuple[str | None, str | None]:
        """Get AWS credentials from environment or system keyring."""
        # Check environment variables first (standard AWS env vars)
        env_access_key = os.environ.get("AWS_ACCESS_KEY_ID")
        env_secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
        if env_access_key and env_secret_key:
            return env_access_key, env_secret_key
        # Fall back to keyring
        access_key = keyring.get_password(KEYRING_SERVICE, KEYRING_AWS_ACCESS_KEY)
        secret_key = keyring.get_password(KEYRING_SERVICE, KEYRING_AWS_SECRET_KEY)
        return access_key, secret_key

    def set_aws_credentials(self, access_key: str, secret_key: str) -> None:
        """Store AWS credentials in the system keyring."""
        keyring.set_password(KEYRING_SERVICE, KEYRING_AWS_ACCESS_KEY, access_key)
        keyring.set_password(KEYRING_SERVICE, KEYRING_AWS_SECRET_KEY, secret_key)

    def clear_aws_credentials(self) -> None:
        """Remove AWS credentials from the keyring."""
        try:
            keyring.delete_password(KEYRING_SERVICE, KEYRING_AWS_ACCESS_KEY)
            keyring.delete_password(KEYRING_SERVICE, KEYRING_AWS_SECRET_KEY)
        except keyring.errors.PasswordDeleteError:
            pass

    def get_google_credentials(self) -> dict | None:
        """Get Google OAuth credentials from the system keyring."""
        creds_json = keyring.get_password(KEYRING_SERVICE, KEYRING_GOOGLE_CREDENTIALS)
        if creds_json:
            return json.loads(creds_json)
        return None

    def set_google_credentials(self, credentials: dict) -> None:
        """Store Google OAuth credentials in the system keyring."""
        keyring.set_password(
            KEYRING_SERVICE, KEYRING_GOOGLE_CREDENTIALS, json.dumps(credentials)
        )

    def get_google_client_config(self) -> dict | None:
        """Get Google OAuth client configuration from the system keyring."""
        config_json = keyring.get_password(KEYRING_SERVICE, KEYRING_GOOGLE_CLIENT_CONFIG)
        if config_json:
            return json.loads(config_json)
        return None

    def set_google_client_config(self, client_config: dict) -> None:
        """Store Google OAuth client configuration in the system keyring."""
        keyring.set_password(
            KEYRING_SERVICE, KEYRING_GOOGLE_CLIENT_CONFIG, json.dumps(client_config)
        )

    def clear_google_credentials(self) -> None:
        """Remove Google credentials from the keyring."""
        try:
            keyring.delete_password(KEYRING_SERVICE, KEYRING_GOOGLE_CREDENTIALS)
        except keyring.errors.PasswordDeleteError:
            pass

    def has_google_drive_configured(self) -> bool:
        """Check if Google Drive integration is configured."""
        return self.get_google_credentials() is not None

    @property
    def ai_provider(self) -> str:
        """Get the configured AI provider."""
        return self._config.get("ai_provider", AI_PROVIDER_ANTHROPIC)

    @ai_provider.setter
    def ai_provider(self, provider: str) -> None:
        """Set the AI provider."""
        if provider not in (AI_PROVIDER_ANTHROPIC, AI_PROVIDER_AWS_BEDROCK):
            raise ValueError(f"Invalid AI provider: {provider}")
        self.set("ai_provider", provider)

    @property
    def aws_region(self) -> str:
        """Get the AWS region for Bedrock."""
        return self._config.get("aws_region", "us-east-1")

    @aws_region.setter
    def aws_region(self, region: str) -> None:
        """Set the AWS region."""
        self.set("aws_region", region)

    def get_db_password(self) -> str | None:
        """Get the database encryption password from the system keyring."""
        return keyring.get_password(KEYRING_SERVICE, KEYRING_DB_PASSWORD)

    @property
    def db_path(self) -> Path:
        """Get the database file path."""
        return self.data_dir / "tax_data.db"

    @property
    def tax_year(self) -> int:
        """Get the current tax year."""
        return self._config.get("tax_year", 2024)

    @tax_year.setter
    def tax_year(self, year: int) -> None:
        """Set the current tax year."""
        self.set("tax_year", year)

    @property
    def state(self) -> str | None:
        """Get the state of residence."""
        return self._config.get("state")

    @state.setter
    def state(self, state: str) -> None:
        """Set the state of residence."""
        self.set("state", state.upper())

    @property
    def use_agent_sdk(self) -> bool:
        """Check if Agent SDK features are enabled."""
        return self._config.get("use_agent_sdk", False)

    @use_agent_sdk.setter
    def use_agent_sdk(self, enabled: bool) -> None:
        """Enable or disable Agent SDK features."""
        self.set("use_agent_sdk", enabled)

    @property
    def agent_sdk_max_turns(self) -> int:
        """Get maximum agentic turns for SDK operations."""
        return self._config.get("agent_sdk_max_turns", 10)

    @agent_sdk_max_turns.setter
    def agent_sdk_max_turns(self, turns: int) -> None:
        """Set maximum agentic turns."""
        self.set("agent_sdk_max_turns", max(1, min(turns, 50)))

    @property
    def agent_sdk_allow_web(self) -> bool:
        """Check if web tools are allowed for Agent SDK."""
        return self._config.get("agent_sdk_allow_web", True)

    @agent_sdk_allow_web.setter
    def agent_sdk_allow_web(self, allowed: bool) -> None:
        """Enable or disable web tools for Agent SDK."""
        self.set("agent_sdk_allow_web", allowed)

    def to_dict(self) -> dict[str, Any]:
        """Return configuration as a dictionary (excluding secrets)."""
        return {k: v for k, v in self._config.items()}


# Global config instance
_config: Config | None = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = Config()
    return _config
