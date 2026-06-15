"""
Image-to-text via a multimodal model served by Ollama (default: LLaVA 7B).

Ollama loads the vision model on demand and evicts it when idle, so it does
not permanently occupy VRAM alongside the text LLM.

Swap the model by changing `vision.model` in config.yaml.
"""
import base64
from pathlib import Path

import ollama

from app.config import cfg


class VisionCaptioner:
    def __init__(self) -> None:
        self._client = ollama.Client(host=cfg.vision.base_url)
        self._model = cfg.vision.model

    def _read_image_b64(self, image_path: str) -> str:
        """Read a local image file and return its base64-encoded bytes."""
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def describe(
        self,
        image_path: str,
        prompt: str = "Describe this image in detail.",
    ) -> str:
        """
        Send an image + text prompt to the vision model.
        Returns the model's text description.

        image_path: absolute or relative path to a .jpg / .png / etc. file
        prompt:     the instruction — customize per use-case
        """
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        response = self._client.chat(
            model=self._model,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                    # Ollama accepts a list of base64 strings under "images".
                    "images": [self._read_image_b64(image_path)],
                }
            ],
        )
        return response.message.content or ""
