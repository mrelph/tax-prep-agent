"""Utilities for loading and writing .env files."""

import os
from pathlib import Path


def get_env_path() -> Path:
    """Get the .env file path (project config dir or cwd)."""
    config_dir = Path.home() / ".tax-agent"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / ".env"


def load_env(env_path: Path | None = None) -> None:
    """Load environment variables from a .env file.

    Only sets variables that are not already set in the environment,
    so real env vars always take precedence.
    """
    path = env_path or get_env_path()
    if not path.exists():
        return

    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            # Remove surrounding quotes if present
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]
            # Only set if not already in environment
            if key not in os.environ:
                os.environ[key] = value


def write_env_key(env_path: Path, key: str, value: str) -> None:
    """Write or update a single key in a .env file.

    Preserves existing keys and comments.
    """
    lines: list[str] = []
    found = False

    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                stripped = line.strip()
                if stripped and not stripped.startswith("#") and "=" in stripped:
                    existing_key = stripped.split("=", 1)[0].strip()
                    if existing_key == key:
                        lines.append(f'{key}="{value}"\n')
                        found = True
                        continue
                lines.append(line)

    if not found:
        if lines and not lines[-1].endswith("\n"):
            lines.append("\n")
        lines.append(f'{key}="{value}"\n')

    env_path.parent.mkdir(parents=True, exist_ok=True)
    with open(env_path, "w") as f:
        f.writelines(lines)
