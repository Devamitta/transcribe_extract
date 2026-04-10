# Gemini API client with multi-key rotation, rate limiting, and retry logic.

import os
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types
from tenacity import (
    retry,
    wait_exponential,
    stop_after_attempt,
    retry_if_exception_type,
)

load_dotenv()

RPM_LIMIT = 5
MIN_REQUEST_INTERVAL = 12
HOURS_TO_RESET = 24

API_KEYS: list[tuple[str, str]] = []
for i in range(1, 100):
    key = os.getenv(f"GEMINI_API_KEY_{i}")
    if key:
        API_KEYS.append((f"GEMINI_API_KEY_{i}", key))

if not API_KEYS:
    key = os.getenv("GEMINI_API_KEY")
    if key:
        API_KEYS.append(("GEMINI_API_KEY", key))

if not API_KEYS:
    print("[ERROR] No GEMINI_API_KEY found in .env")
    exit(1)

print(f"Loaded {len(API_KEYS)} API keys: {[k[0] for k in API_KEYS]}", flush=True)


class KeyManager:
    def __init__(self, keys: list[tuple[str, str]]):
        self.keys = keys
        self.current_index = 0
        self.client = genai.Client(api_key=self.keys[0][1])
        self.current_key_name = self.keys[0][0]
        self.failed_keys: dict[int, float] = {}
        self.last_request_time = 0.0

    def test_current_key(self, model: str) -> bool:
        try:
            print(f"Testing key {self.current_key_name}...", flush=True)
            response = self.client.models.generate_content(
                model=model,
                contents="hi",
                config=types.GenerateContentConfig(
                    max_output_tokens=5, temperature=0.0
                ),
            )
            if response.text:
                print(f"[OK] {self.current_key_name} works", flush=True)
                return True
            return False
        except Exception as e:
            print(f"[ERROR] {self.current_key_name} failed: {e}", flush=True)
            return False

    def switch_to_next_key(self) -> bool:
        original_index = self.current_index
        while True:
            self.current_index = (self.current_index + 1) % len(self.keys)
            failure_time = self.failed_keys.get(self.current_index)
            if failure_time:
                hours_since_failure = (time.time() - failure_time) / 3600
                if hours_since_failure >= HOURS_TO_RESET:
                    print(f"Key reset after {hours_since_failure:.1f}h", flush=True)
                    del self.failed_keys[self.current_index]
                    break
                if self.current_index == original_index:
                    print(
                        f"[ERROR] All keys failed. Wait {HOURS_TO_RESET}h", flush=True
                    )
                    return False
                continue
            break

        key_name, key_value = self.keys[self.current_index]
        self.current_key_name = key_name
        self.client = genai.Client(api_key=key_value)
        print(f"Switched to {self.current_key_name}", flush=True)
        print("Waiting 3s...", flush=True)
        time.sleep(3)
        return True

    def handle_quota_error(self) -> bool:
        print(f"{self.current_key_name} quota exceeded, switching...", flush=True)
        self.failed_keys[self.current_index] = time.time()
        return self.switch_to_next_key()

    def wait_for_rate_limit(self) -> None:
        elapsed = time.time() - self.last_request_time
        if elapsed < MIN_REQUEST_INTERVAL:
            wait = MIN_REQUEST_INTERVAL - elapsed
            print(f"Rate limiting: waiting {wait:.1f}s...", flush=True)
            time.sleep(wait)
        self.last_request_time = time.time()


key_manager = KeyManager(API_KEYS)


def get_working_key(model: str = "gemini-2.5-flash") -> bool:
    """Test and find a working API key."""
    for _ in range(len(key_manager.keys)):
        if key_manager.test_current_key(model):
            return True
        if not key_manager.switch_to_next_key():
            break
    return False


@retry(
    wait=wait_exponential(multiplier=2, min=4, max=60),
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type(Exception),
)
def generate_content(
    contents: str,
    system_instruction: str,
    model: str,
    max_output_tokens: int = 32768,
    temperature: float = 0.1,
) -> str:
    """Generate content using Gemini API with key rotation and rate limiting."""
    key_manager.wait_for_rate_limit()
    print(f"  -> {key_manager.current_key_name}...", flush=True)

    try:
        response = key_manager.client.models.generate_content(
            model=model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
            ),
        )
    except Exception as e:
        if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
            if not key_manager.handle_quota_error():
                raise Exception("All API keys exhausted")
        raise
    if response.text is None:
        raise ValueError("Empty response from Gemini API")
    return response.text


def list_models() -> list[str]:
    """List all available Gemini models for the current key."""
    client = genai.Client(api_key=API_KEYS[0][1])
    models = [model.name for model in client.models.list() if model.name]
    return sorted(models)


if __name__ == "__main__":
    import sys

    show_all = "--all" in sys.argv or "-a" in sys.argv
    models = list_models()

    print(f"=== GEMINI MODELS ({len(models)}) ===")
    for m in models:
        print(f"  {m}")
