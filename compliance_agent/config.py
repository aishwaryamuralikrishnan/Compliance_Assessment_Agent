"""Environment and YAML configuration.

Secrets come from the process environment. `.env` (if present) is loaded with
`override=False`, so a value already exported in the OS environment -- in particular
OPENROUTER_API_KEY -- always wins over the file.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"

load_dotenv(ROOT / ".env", override=False)


class ConfigError(RuntimeError):
    pass


def env(name: str, default: str | None = None, *, required: bool = False) -> str | None:
    value = os.environ.get(name, default)
    if required and not value:
        raise ConfigError(
            f"Environment variable {name} is not set. "
            f"Export it in your shell / VS Code terminal (or put it in .env)."
        )
    return value


def openrouter_api_key() -> str:
    return env("OPENROUTER_API_KEY", required=True)  # type: ignore[return-value]


def openrouter_base_url() -> str:
    return (env("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1").rstrip("/")


def database_url() -> str:
    url = env("DATABASE_URL")
    if url:
        return url
    user = env("POSTGRES_USER", "compliance")
    pwd = env("POSTGRES_PASSWORD", "compliance")
    db = env("POSTGRES_DB", "compliance")
    port = env("POSTGRES_PORT", "5432")
    return f"postgresql://{user}:{pwd}@localhost:{port}/{db}"


def langsmith_enabled() -> bool:
    return (env("LANGSMITH_TRACING") or env("LANGCHAIN_TRACING_V2") or "false").lower() in ("1", "true", "yes")


@lru_cache(maxsize=None)
def load_yaml(name: str) -> dict[str, Any]:
    path = CONFIG_DIR / name
    if not path.exists():
        raise ConfigError(f"Missing config file: {path}")
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def models_config() -> dict[str, Any]:
    return load_yaml("models.yaml")


def roles_config() -> dict[str, Any]:
    return load_yaml("roles.yaml")


def corpus_config() -> dict[str, Any]:
    return load_yaml("corpus.yaml")
