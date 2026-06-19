"""Image generation provider abstraction for OpenRouter FLUX."""

import base64
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

from tools.printer import printer as pr

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_IMAGE_MODEL = "black-forest-labs/flux.2-pro"
OPENROUTER_IMAGE_TIMEOUT = 180


def _generate_image_openrouter(prompt: str, output_path: Path) -> None:
    """Generate image using OpenRouter FLUX."""
    if not OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY not set in environment.")

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://sasanarakkha.org",
        "X-Title": "DPS Transcriber",
    }
    payload = {
        "model": OPENROUTER_IMAGE_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "modalities": ["image"],
        "image_config": {"aspect_ratio": "16:9"},
    }

    pr.white(
        "  -> openrouter image "
        f"{OPENROUTER_IMAGE_MODEL} (timeout={OPENROUTER_IMAGE_TIMEOUT}s)..."
    )
    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=OPENROUTER_IMAGE_TIMEOUT,
    )
    if response.status_code != 200:
        raise ValueError(
            f"OpenRouter image generation failed: {response.status_code} - {response.text}"
        )

    data = response.json()
    try:
        data_url: str = data["choices"][0]["message"]["images"][0]["image_url"]["url"]
    except (KeyError, IndexError) as exc:
        raise ValueError(f"Unexpected OpenRouter response: {data}") from exc

    # data_url is "data:image/jpeg;base64,<data>"
    b64_data = data_url.split(",", 1)[1]
    output_path.write_bytes(base64.b64decode(b64_data))


def generate_image(prompt: str, output_path: Path) -> None:
    """Generate an image using the OpenRouter provider."""
    _generate_image_openrouter(prompt, output_path)
