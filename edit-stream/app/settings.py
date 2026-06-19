"""
Single source of truth for all backend configuration.

Loaded from environment variables (and an optional .env file) via
pydantic-settings — the standard, proven approach. No hand-rolled parsing,
no scattered `os.environ` reads anywhere else in this codebase; every other
module imports `settings` from here.
"""
from __future__ import annotations

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Secret, env-only, no default: `SecretStr` never reveals its value via
    # str()/repr() (verified: a model containing it prints
    # "key=SecretStr('**********')"), so even an accidental `print(settings)`
    # or log statement can't leak it. The raw value is only retrievable via
    # `.get_secret_value()`, called in exactly one place — see
    # anthropic_provider.py.
    anthropic_api_key: SecretStr

    # claude-sonnet-4-6: current Sonnet-class model, the "best combination
    # of speed and intelligence" per docs.claude.com (verified 2026-06-19).
    # Override via the MODEL env var — no other module hardcodes a model id.
    model: str = "claude-sonnet-4-6"

    # Caps tool-input + any model commentary tokens. This is a cost guard,
    # not just an output-length knob.
    max_output_tokens: int = 4096

    request_timeout_s: float = 60.0

    # The SEARCH/REPLACE block grammar shown to the model lives here, not
    # hardcoded in anthropic_provider.py, so the diff format has exactly one
    # place to change.
    search_marker: str = "<<<<<<< SEARCH"
    divider_marker: str = "======="
    replace_marker: str = ">>>>>>> REPLACE"


settings = Settings()
