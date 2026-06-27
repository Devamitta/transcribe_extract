# OpenRouter API client for accessing various LLM models with rate limiting and retry logic.

import base64
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from tools.openai_compat import RateLimiter, extract_content, post_chat_completion

load_dotenv()

API_KEY = os.getenv("OPENROUTER_API_KEY")
if not API_KEY:
    print("[ERROR] No OPENROUTER_API_KEY found in .env")
    exit(1)

print("Loaded OPENROUTER_API_KEY", flush=True)

HOURS_TO_RESET = 24


class OpenRouterClient(RateLimiter):
    def __init__(self, api_key: str):
        super().__init__()
        self.api_key = api_key
        self.base_url = "https://openrouter.ai/api/v1"
        self.failed_models: dict[str, float] = {}

    def handle_rate_limit_error(self, model: str) -> bool:
        print(f"{model} rate limited, trying next...", flush=True)
        self.failed_models[model] = time.time()
        return True


client = OpenRouterClient(API_KEY)


def get_working_key() -> bool:
    """Test if the API key works using the auth/key endpoint."""
    try:
        print("Testing OpenRouter API key...", flush=True)
        client.wait_for_rate_limit()
        resp = requests.get(
            f"{client.base_url}/auth/key",
            headers={
                "Authorization": f"Bearer {client.api_key}",
            },
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            label = data.get("data", {}).get("label", "unnamed")
            print(f"[OK] OPENROUTER_API_KEY works (Key: {label})", flush=True)
            return True
        print(f"[ERROR] OpenRouter API key failed: {resp.status_code}", flush=True)
        return False
    except Exception as e:
        print(f"[ERROR] OpenRouter API key failed: {e}", flush=True)
        return False


@retry(
    wait=wait_exponential(multiplier=2, min=4, max=60),
    stop=stop_after_attempt(
        2
    ),  # Reduced attempts since we will fallback to other models
    retry=retry_if_exception_type((requests.exceptions.RequestException, ValueError)),
)
def generate_content(
    contents: str,
    system_instruction: str,
    model: str,
    max_output_tokens: int = 32768,
    temperature: float = 0.1,
    timeout: int = 15,  # Added timeout parameter with 15s default
) -> str:
    """Generate content using OpenRouter API."""
    client.wait_for_rate_limit()

    try:
        resp = post_chat_completion(
            base_url=client.base_url,
            api_key=client.api_key,
            model=model,
            system_instruction=system_instruction,
            contents=contents,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
            timeout=timeout,
            extra_headers={
                "HTTP-Referer": "https://localhost",
                "X-Title": "Dhamma Extract",
            },
        )
    except requests.exceptions.Timeout:
        raise  # already logged by post_chat_completion
    except Exception as e:
        if "429" in str(e) or "rate_limit" in str(e).lower():
            client.handle_rate_limit_error(model)
        raise

    if resp.status_code != 200:
        raise ValueError(f"OpenRouter API error: {resp.status_code} {resp.text}")

    return extract_content(resp.json(), "OpenRouter")


def transcribe_audio_clip(
    clip_path: Path,
    garbled_text: str,
    context_text: str,
    glossary: str,
    model: str = "google/gemini-2.5-flash",
    fallback_model: str = "google/gemini-2.5-pro",
) -> str:
    """Re-transcribe just the garbled span within a short audio clip.

    The clip is padded ±15s around the garbled span, so it contains surrounding
    speech beyond the span itself. The model is told exactly which short
    Whisper-garbled phrase to fix and must return only the corrected replacement
    for that phrase, not a transcription of the whole clip. Falls back to
    fallback_model once on error or an empty/low-confidence result from the
    primary model.
    """
    audio_b64 = base64.b64encode(clip_path.read_bytes()).decode("utf-8")
    system_instruction = (
        "You are correcting a Whisper transcription error from a Buddhist Dhamma "
        "talk or meditation interview. The attached audio clip is a ~30s window "
        "padded around a short garbled phrase. Listen to the clip and find the "
        "moment that produced the garbled phrase given below, then reply with "
        "ONLY the corrected transcription of that short phrase (not the rest of "
        "the clip, not commentary). Use the surrounding transcript and glossary "
        "only to disambiguate Pali terms — do not invent words that are not "
        "actually spoken. If you cannot confidently identify the corresponding "
        "audio moment, reply with the original garbled phrase unchanged."
    )
    contents = [
        {
            "type": "text",
            "text": (
                f"Garbled phrase to fix: {garbled_text!r}\n\n"
                f"Surrounding transcript context:\n{context_text}\n\n"
                f"Pali glossary:\n{glossary}\n\n"
                "Listen to the attached audio clip and return only the corrected "
                "replacement for the garbled phrase."
            ),
        },
        {
            "type": "input_audio",
            "input_audio": {"data": audio_b64, "format": "mp3"},
        },
    ]

    def _call(use_model: str) -> str:
        client.wait_for_rate_limit()
        resp = post_chat_completion(
            base_url=client.base_url,
            api_key=client.api_key,
            model=use_model,
            system_instruction=system_instruction,
            contents=contents,
            max_output_tokens=1024,
            temperature=0.1,
            timeout=60,
            extra_headers={
                "HTTP-Referer": "https://localhost",
                "X-Title": "Dhamma Extract",
            },
        )
        if resp.status_code != 200:
            raise ValueError(f"OpenRouter API error: {resp.status_code} {resp.text}")
        return extract_content(resp.json(), "OpenRouter")

    try:
        result = _call(model)
    except Exception as e:
        print(f"  [{model}] failed ({e}), retrying with {fallback_model}", flush=True)
        return _call(fallback_model)

    if not result.strip():
        print(f"  [{model}] empty result, retrying with {fallback_model}", flush=True)
        return _call(fallback_model)

    return result


def list_models(free_only: bool = True) -> list[str]:
    """List available OpenRouter models.

    Args:
        free_only: If True, return only free models (ending with :free).
                 If False, return all models.
    """
    try:
        resp = requests.get(
            "https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {API_KEY}"},
            timeout=30,
        )
        if resp.status_code != 200:
            print(f"Error fetching models: {resp.status_code}")
            return []

        data = resp.json()
        models = []
        for m in data.get("data", []):
            model_id = m["id"]
            if free_only:
                if model_id.endswith(":free"):
                    models.append(model_id)
            else:
                models.append(model_id)
        return sorted(models)
    except Exception as e:
        print(f"Error fetching models: {e}")
        return []


if __name__ == "__main__":
    import sys

    show_all = "--all" in sys.argv or "-a" in sys.argv
    free_models = list_models(free_only=True)
    all_models = list_models(free_only=False)

    if show_all:
        print(f"=== FREE MODELS ({len(free_models)}) ===")
        for m in free_models:
            print(f"  {m}")
        print(f"\n=== ALL MODELS ({len(all_models)}) ===")
        for m in all_models:
            print(f"  {m}")
    else:
        print(f"=== FREE MODELS ({len(free_models)}) ===")
        for m in free_models:
            print(f"  {m}")
        print(f"\nUse --all to see all {len(all_models)} models")
