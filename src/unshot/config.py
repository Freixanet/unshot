"""Flat configuration loaded from environment / .env.

Deliberately model-agnostic: there are no presets and no allow-lists of model
names. Whatever string you put in PROMPT_MODEL / IMAGE_MODEL is passed through
to the provider untouched.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, fields, replace
from pathlib import Path

from dotenv import dotenv_values

PROVIDERS = ("gemini", "openai")


class ConfigError(ValueError):
    """Raised when required configuration is missing or invalid."""


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


@dataclass(frozen=True)
class Settings:
    prompt_provider: str = "gemini"
    prompt_model: str | None = None
    prompt_thinking: str | None = None
    image_model: str | None = None
    image_quality: str | None = None
    image_size: str | None = None
    image_input_fidelity: str | None = None
    gemini_api_key: str | None = None
    openai_api_key: str | None = None
    telegram_bot_token: str | None = None
    telegram_allowed_users: frozenset[int] = frozenset()

    def with_overrides(self, **overrides: str | None) -> "Settings":
        """Return a copy where every non-empty override replaces the current value."""
        valid = {f.name for f in fields(self)}
        unknown = set(overrides) - valid
        if unknown:
            raise ConfigError(f"Unknown setting(s): {', '.join(sorted(unknown))}")
        changes = {k: _clean(v) for k, v in overrides.items() if _clean(v) is not None}
        new = replace(self, **changes)
        new.validate_provider()
        return new

    def validate_provider(self) -> None:
        if self.prompt_provider not in PROVIDERS:
            raise ConfigError(
                f"PROMPT_PROVIDER must be one of {PROVIDERS}, got {self.prompt_provider!r}"
            )

    def require(self, *names: str) -> None:
        """Fail with a clear message listing every missing required setting."""
        missing = [n.upper() for n in names if not getattr(self, n)]
        if missing:
            raise ConfigError(
                "Missing required configuration: "
                + ", ".join(missing)
                + ". Set them in .env (see .env.example) or pass the matching CLI flag."
            )

    def require_for_generation(self) -> None:
        key = "gemini_api_key" if self.prompt_provider == "gemini" else "openai_api_key"
        self.require("prompt_model", "image_model", key, "openai_api_key")


def _parse_user_ids(raw: str | None) -> frozenset[int]:
    if not raw:
        return frozenset()
    try:
        return frozenset(int(x) for x in raw.replace(" ", "").split(",") if x)
    except ValueError as exc:
        raise ConfigError("TELEGRAM_ALLOWED_USERS must be comma-separated numeric user ids") from exc


def load_settings(
    env_file: str | os.PathLike[str] | None = ".env",
    environ: Mapping[str, str] | None = None,
) -> Settings:
    """Build Settings from a .env file overlaid by real environment variables.

    Real environment variables win over the .env file, so deployments can
    override anything without editing files.
    """
    values: dict[str, str | None] = {}
    if env_file and Path(env_file).is_file():
        values.update(dotenv_values(env_file))
    values.update(os.environ if environ is None else environ)

    def get(name: str) -> str | None:
        return _clean(values.get(name))

    settings = Settings(
        prompt_provider=(get("PROMPT_PROVIDER") or "gemini").lower(),
        prompt_model=get("PROMPT_MODEL"),
        prompt_thinking=get("PROMPT_THINKING"),
        image_model=get("IMAGE_MODEL"),
        image_quality=get("IMAGE_QUALITY"),
        image_size=get("IMAGE_SIZE"),
        image_input_fidelity=get("IMAGE_INPUT_FIDELITY"),
        gemini_api_key=get("GEMINI_API_KEY"),
        openai_api_key=get("OPENAI_API_KEY"),
        telegram_bot_token=get("TELEGRAM_BOT_TOKEN"),
        telegram_allowed_users=_parse_user_ids(get("TELEGRAM_ALLOWED_USERS")),
    )
    settings.validate_provider()
    return settings
