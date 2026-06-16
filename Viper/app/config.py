"""
Typed configuration loader.
Reads config.yaml once and exposes a singleton `cfg` imported everywhere.
To change any setting, edit config.yaml — no Python changes needed.
"""
from pathlib import Path
from typing import List, Optional

import yaml
from pydantic import BaseModel


# ── Nested options models ──────────────────────────────────────────────────────
# All fields Optional — only keys explicitly set in config.yaml are forwarded
# to Ollama. Unset keys fall through to whatever the Modelfile baked in.
# Resolution logic lives in app/model_options.py (single source of truth).

class LLMOptions(BaseModel):
    temperature: Optional[float] = None
    num_ctx: Optional[int] = None
    seed: Optional[int] = None
    stop: Optional[List[str]] = None
    repeat_penalty: Optional[float] = None
    num_predict: Optional[int] = None


class VisionOptions(BaseModel):
    temperature: Optional[float] = None
    num_ctx: Optional[int] = None
    seed: Optional[int] = None
    stop: Optional[List[str]] = None
    repeat_penalty: Optional[float] = None
    num_predict: Optional[int] = None


# ── Top-level config models ────────────────────────────────────────────────────

class LLMConfig(BaseModel):
    model: str
    base_url: str
    # Flat convenience keys kept Optional for backward compat with existing
    # config.yaml files that set them at the top level.  If both flat keys
    # and an `options` block are present, the options block wins (see
    # app/model_options.llm_options_from_config for the merge order).
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    # New optional fields — omitting them preserves existing behaviour.
    system_prompt: Optional[str] = None
    options: Optional[LLMOptions] = None
    # NOTE: `format` constrains JSON *syntax*, not content correctness.
    # Requires Ollama >= 0.1.9.  Targeting the legacy "json" string value
    # for maximum compatibility; JSON-schema objects require Ollama >= 0.5.x.
    format: Optional[str] = None


class VisionConfig(BaseModel):
    model: str
    base_url: str
    system_prompt: Optional[str] = None
    options: Optional[VisionOptions] = None


class EmbeddingsConfig(BaseModel):
    model: str
    device: str


class RAGConfig(BaseModel):
    chunk_size: int
    chunk_overlap: int
    top_k: int
    chroma_persist_dir: str
    collection_name: str = "viper_docs"


class APIConfig(BaseModel):
    enabled: bool = True   # false = in-process use only; true = also serve over HTTP
    host: str
    port: int
    reload: bool


class Config(BaseModel):
    llm: LLMConfig
    vision: VisionConfig
    embeddings: EmbeddingsConfig
    rag: RAGConfig
    api: APIConfig


def load_config(path: str = "config.yaml") -> Config:
    config_path = Path(path)
    if not config_path.exists():
        # Fall back to the file next to this module's grandparent (project root).
        config_path = Path(__file__).parent.parent / "config.yaml"
    with open(config_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return Config(**data)


# Loaded once at import time; all modules import this singleton.
cfg = load_config()
