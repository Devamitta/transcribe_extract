# Uploads a prepared JSONL file to OpenAI and creates a Batch API job.

import datetime
import json
import sys
from pathlib import Path

from tools.openai_client import upload_batch_file, create_batch


def main():
    if len(sys.argv) < 2:
        print("Usage: uv run python scripts/batch_submit.py path/to/file.jsonl")
        sys.exit(1)

    jsonl_path = Path(sys.argv[1])
    if not jsonl_path.exists():
        print(f"File not found: {jsonl_path}")
        sys.exit(1)

    if jsonl_path.suffix != ".jsonl":
        print(f"Error: {jsonl_path} is not a .jsonl file")
        sys.exit(1)

    with open(jsonl_path, "r", encoding="utf-8") as f:
        count = sum(1 for _ in f)

    print(f"Submitting {count} requests from {jsonl_path.name}...")

    file_id = upload_batch_file(jsonl_path)
    print(f"Uploaded file ID: {file_id}")

    batch_id = create_batch(file_id)
    print(f"Created batch ID: {batch_id}")

    # Determine task from filename
    stem = jsonl_path.stem.lower()
    if stem.startswith("pali"):
        task = "pali"
    elif stem.startswith("extract"):
        task = "extract"
    else:
        task = "unknown"

    jobs_path = Path("output/batch_jobs.json")
    jobs = json.loads(jobs_path.read_text()) if jobs_path.exists() else []

    jobs.append(
        {
            "batch_id": batch_id,
            "task": task,
            "jsonl_path": str(jsonl_path),
            "submitted_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "status": "submitted",
        }
    )

    output_dir = jobs_path.parent
    output_dir.mkdir(exist_ok=True, parents=True)
    jobs_path.write_text(json.dumps(jobs, indent=2, ensure_ascii=False))

    print(f"Saved to {jobs_path}")
    print(
        f"Check status: uv run python scripts/batch_retrieve.py --batch-id {batch_id}"
    )


if __name__ == "__main__":
    main()
