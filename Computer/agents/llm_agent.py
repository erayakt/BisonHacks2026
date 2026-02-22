from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv


@dataclass(frozen=True)
class LlmAgentConfig:
    model_name: str = "gemini-2.5-flash"
    default_prompt: str = (
        "Describe this cropped image region in 2 to 4 short sentences. "
        "Focus on what is visually present and any important textures/patterns. "
        "Avoid guessing details that are not visible."
    )


class LlmAgent:
    """Small wrapper around Gemini (google-genai) for describing an image region.

    This is intentionally minimal:
      - loads GOOGLE_API_KEY from .env
      - sends [prompt, image] to the model
      - returns response.text (string)
    """

    def __init__(self, config: Optional[LlmAgentConfig] = None):
        load_dotenv()
        self.config = config or LlmAgentConfig()

        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not found in environment variables (.env).")

        try:
            from google import genai  # google-genai
        except Exception as e:
            raise ImportError(
                "Missing dependency for Gemini image calls. Install: pip install google-genai"
            ) from e

        self._client = genai.Client(api_key=api_key)

    def describe_image(self, image_path: str, prompt: Optional[str] = None) -> str:
        """Describe an image at `image_path`. Returns plain text."""
        from PIL import Image  # pillow

        p = (prompt or self.config.default_prompt).strip()
        if not p:
            p = self.config.default_prompt

        img = Image.open(image_path)

        resp = self._client.models.generate_content(
            model=self.config.model_name,
            contents=[p, img],
        )
        return (resp.text or "").strip()
