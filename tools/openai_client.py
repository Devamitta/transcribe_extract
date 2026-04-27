# OpenAI API client for batch processing — upload, submit, poll, and download batch jobs.

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

_API_KEY = os.getenv("OPENAI_API_KEY")
if not _API_KEY:
    raise EnvironmentError("OPENAI_API_KEY not set in .env")

_client = OpenAI(api_key=_API_KEY)


def prepare_batch_request(
    custom_id: str,
    system_instruction: str,
    user_content: str,
    model: str,
) -> dict:
    return {
        "custom_id": custom_id,
        "method": "POST",
        "url": "/v1/chat/completions",
        "body": {
            "model": model,
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_content},
            ],
        },
    }


def upload_batch_file(jsonl_path: Path) -> str:
    """Upload JSONL to OpenAI Files API; return file_id."""
    with open(jsonl_path, "rb") as f:
        response = _client.files.create(file=f, purpose="batch")
    return response.id


def create_batch(file_id: str) -> str:
    """Submit a batch job with 24h window; return batch_id."""
    response = _client.batches.create(
        input_file_id=file_id,
        endpoint="/v1/chat/completions",
        completion_window="24h",
    )
    return response.id


def get_batch_status(batch_id: str) -> dict:
    """Return {id, status, request_counts: {total, completed, failed}}."""
    info = _client.batches.retrieve(batch_id)
    counts = info.request_counts
    return {
        "id": info.id,
        "status": info.status,
        "request_counts": {
            "total": getattr(counts, "total", 0),
            "completed": getattr(counts, "completed", 0),
            "failed": getattr(counts, "failed", 0),
        },
        "output_file_id": info.output_file_id,
    }


def download_results(batch_id: str) -> list[dict]:
    """Download output file for a completed batch; return parsed result dicts."""
    info = _client.batches.retrieve(batch_id)
    if not info.output_file_id:
        raise ValueError(f"No output file for batch {batch_id}")
    content = _client.files.content(info.output_file_id).text
    return [json.loads(line) for line in content.splitlines() if line.strip()]
