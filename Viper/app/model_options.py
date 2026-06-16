"""
Shared Ollama options resolver — single source of truth.

RULE: Both app/llm/inference.py and capabilities/llm.py MUST import from
here.  Neither may build its own options dict.  The comment in each file
says so explicitly.

Merge priority (highest wins):
  1. per-call keyword overrides  (e.g. temperature=0 for a specific call)
  2. cfg.llm.options block       (nested LLMOptions in config.yaml)
  3. cfg.llm.temperature / cfg.llm.max_tokens  (flat legacy keys)
  4. Modelfile baked-in PARAMETER defaults     (Ollama applies these when
     a key is absent from the dict we send — we never send None)

Only non-None values are forwarded, so any key absent from both config and
the per-call overrides falls through to whatever the Modelfile baked in.
Sending an empty dict {} is identical to sending nothing — Ollama uses its
own defaults in both cases.
"""
from typing import Any, Dict, List, Optional


def llm_options_from_config(cfg_llm) -> Dict[str, Any]:
    """
    Build a base options dict from LLMConfig.

    Layer 1: flat convenience keys (temperature, max_tokens → num_predict).
    Layer 2: nested options block — overwrites any flat key it also sets,
    giving a migration path from flat → nested without requiring the flat
    keys to be removed on day one.
    """
    opts: Dict[str, Any] = {}

    if cfg_llm.temperature is not None:
        opts["temperature"] = cfg_llm.temperature
    if cfg_llm.max_tokens is not None:
        opts["num_predict"] = cfg_llm.max_tokens

    if cfg_llm.options is not None:
        opts.update(cfg_llm.options.model_dump(exclude_none=True))

    return opts


def vision_options_from_config(cfg_vision) -> Dict[str, Any]:
    """Build a base options dict from VisionConfig."""
    opts: Dict[str, Any] = {}
    if cfg_vision.options is not None:
        opts.update(cfg_vision.options.model_dump(exclude_none=True))
    return opts


def resolve_llm_options(cfg_llm, **call_overrides: Any) -> Dict[str, Any]:
    """
    Merge config-level LLM options with per-call overrides.

    call_overrides keys follow Ollama naming conventions:
        temperature, num_predict, seed, num_ctx, repeat_penalty, stop

    Example — force determinism for a single tool-calling turn:
        resolve_llm_options(cfg.llm, temperature=0, seed=42)
    """
    opts = llm_options_from_config(cfg_llm)
    for key, val in call_overrides.items():
        if val is not None:
            opts[key] = val
    return opts


def resolve_vision_options(cfg_vision, **call_overrides: Any) -> Dict[str, Any]:
    """Merge config-level vision options with per-call overrides."""
    opts = vision_options_from_config(cfg_vision)
    for key, val in call_overrides.items():
        if val is not None:
            opts[key] = val
    return opts


def maybe_inject_system(
    messages: List[dict], system_prompt: Optional[str]
) -> List[dict]:
    """
    Prepend a system message ONLY when both conditions hold:
      - system_prompt is not None
      - messages[0] is not already role='system'

    Returns a new list; the original is never mutated.  This prevents double
    injection when the caller (e.g. app/router.py) has already hard-coded a
    system message for that specific method.  The caller's system message
    always takes priority over the config-level default.
    """
    if system_prompt is None:
        return messages
    if messages and messages[0].get("role") == "system":
        return messages
    return [{"role": "system", "content": system_prompt}] + list(messages)
