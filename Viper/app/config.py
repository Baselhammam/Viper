"""
Typed configuration loader.
Reads config.yaml once and exposes a singleton `cfg` imported everywhere.
To change any setting, edit config.yaml — no Python changes needed.
"""
from pathlib import Path
from typing import List

import yaml
from pydantic import BaseModel


class LLMConfig(BaseModel):
    model: str
    temperature: float
    max_tokens: int
    base_url: str


class VisionConfig(BaseModel):
    model: str
    base_url: str


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
