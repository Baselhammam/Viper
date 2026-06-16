"""
Vision capability — LLaVA via Ollama implementation.

Provides two operations:
  describe() — natural-language description of an image (flexible prompt)
  ocr()      — extract all visible text verbatim (specialised prompt)

Both work by sending the image as base64 to a multimodal model served by
Ollama.  Swap the model in config.yaml (vision.model).

VRAM note: LLaVA 7B Q4 ≈ 4.5 GB.  Ollama evicts it when idle, so it does
not permanently compete with the LLM for VRAM.
"""
import base64
from pathlib import Path

import ollama

from app.config import cfg
from app.model_options import maybe_inject_system, resolve_vision_options
from capabilities.interfaces import VisionCapability


class OllamaVision(VisionCapability):
    """VisionCapability backed by a multimodal model served by Ollama."""

    def __init__(self) -> None:
        self._client = ollama.Client(host=cfg.vision.base_url)
        self._model = cfg.vision.model

    # ── VisionCapability interface ─────────────────────────────────────────────

    def describe(
        self,
        image_path: str,
        prompt: str = "Describe this image in detail.",
    ) -> str:
        """
        Send the image at image_path to the vision model with the given prompt.
        Returns the model's text response.

        image_path: local file path (.jpg, .png, .bmp, etc.)
        prompt:     tailor this for your use case — e.g. "List every UI element"
                    for a screenshot, or "What does this chart show?" for a graph.
        """
        self._validate(image_path)
        user_message = {
            "role": "user",
            "content": prompt,
            # Ollama expects a list of base64-encoded image strings.
            "images": [self._to_b64(image_path)],
        }
        messages = maybe_inject_system([user_message], cfg.vision.system_prompt)
        options = resolve_vision_options(cfg.vision)

        response = self._client.chat(
            model=self._model,
            messages=messages,
            options=options if options else None,
        )
        return response.message.content or ""

    def ocr(self, image_path: str) -> str:
        """
        Extract all visible text from image_path exactly as it appears on screen.
        Uses a targeted prompt that tells the model to output raw text only.

        Good for: screenshots of terminals, PDF pages, error dialogs, form fields.
        """
        prompt = (
            "Extract ALL text visible in this image exactly as it appears. "
            "Output only the raw text — no commentary, no formatting, no explanations."
        )
        return self.describe(image_path, prompt)

    # ── Internal helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _validate(image_path: str) -> None:
        if not Path(image_path).exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

    @staticmethod
    def _to_b64(image_path: str) -> str:
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
