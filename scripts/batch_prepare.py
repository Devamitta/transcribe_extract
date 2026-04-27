# Prepares OpenAI Batch API JSONL files for the Pali correction and Dhamma extraction pipeline stages.

import argparse
import datetime
import json
import os
import sys
from pathlib import Path

from tools.pali import PALI_SYSTEM_INSTRUCTION, chunk_text_no_overlap
from tools.extract import EXTRACT_SYSTEM_INSTRUCTION, chunk_text
from tools.openai_client import prepare_batch_request

TASK_CONFIG = {
    "pali": {
        "input_dir": Path("output/transcribed"),
        "output_dir": Path("output/corrected_pali"),
        "system_instruction": PALI_SYSTEM_INSTRUCTION,
        "chunk_fn": chunk_text_no_overlap,
        "model_env": "OPENAI_PALI_MODEL",
    },
    "extract": {
        "input_dir": Path("output/corrected_pali"),
        "output_dir": Path("output/extracted"),
        "system_instruction": EXTRACT_SYSTEM_INSTRUCTION,
        "chunk_fn": chunk_text,
        "model_env": "OPENAI_EXTRACT_MODEL",
    },
}


def main():
    parser = argparse.ArgumentParser(
        description="Prepare OpenAI Batch API JSONL for pali correction or dhamma extraction."
    )
    parser.add_argument("task", choices=list(TASK_CONFIG.keys()))
    parser.add_argument("path", nargs="?", help="Optional file or directory to process")
    parser.add_argument(
        "--limit",
        type=int,
        metavar="N",
        help="Process at most N files (applied after skip)",
    )
    args = parser.parse_args()

    task = args.task
    config = TASK_CONFIG[task]
    specific_path = args.path

    if specific_path:
        path = Path(specific_path)
        if not path.exists():
            # Try relative to input_dir
            path = config["input_dir"] / specific_path

        if not path.exists():
            print(f"Path not found: {specific_path}")
            sys.exit(1)

        if path.is_dir():
            md_files = sorted(list(path.rglob("*.md")))
        else:
            md_files = [path]
    else:
        md_files = sorted(list(config["input_dir"].rglob("*.md")))

    if not md_files:
        print(f"No .md files found for task '{task}'.")
        sys.exit(0)

    model = os.getenv(config["model_env"], "gpt-4o-mini")

    queue = []
    skipped = 0
    for file_path in md_files:
        # Determine relative output path to check for existence
        try:
            rel = file_path.relative_to(config["input_dir"])
            output_path = config["output_dir"] / rel
        except ValueError:
            output_path = config["output_dir"] / file_path.name
        output_path_flat = config["output_dir"] / file_path.name

        if output_path.exists() or output_path_flat.exists():
            print(f"[SKIP] {file_path.name}")
            skipped += 1
        else:
            print(f"[QUEUE] {file_path.name}")
            queue.append(file_path)

    print(f"\n{skipped} already done, {len(queue)} to process")

    if args.limit and len(queue) > args.limit:
        print(f"Limiting to first {args.limit} files (--limit).")
        queue = queue[: args.limit]

    if not queue:
        print("Nothing to prepare.")
        sys.exit(0)

    output_dir = Path("output/batch_input")
    output_dir.mkdir(exist_ok=True, parents=True)

    date_str = datetime.date.today().isoformat()
    jsonl_path = output_dir / f"{task}_{date_str}.jsonl"

    counter = 1
    while jsonl_path.exists():
        counter += 1
        jsonl_path = output_dir / f"{task}_{date_str}_{counter}.jsonl"

    total_chunks = 0
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for file_path in queue:
            try:
                rel_stem = str(
                    file_path.relative_to(config["input_dir"]).with_suffix("")
                )
            except ValueError:
                rel_stem = file_path.stem
            if "__" in rel_stem:
                print(f"Warning: path contains '__' delimiter: {file_path}")
            text = file_path.read_text(encoding="utf-8")
            chunks = config["chunk_fn"](text)
            for i, chunk in enumerate(chunks):
                custom_id = f"{task}__{rel_stem}__{i:04d}"
                record = prepare_batch_request(
                    custom_id, config["system_instruction"], chunk, model
                )
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                total_chunks += 1

    print(f"\nWritten {total_chunks} requests to {jsonl_path}")
    print(f"Files: {len(queue)}  Model: {model}")
    print(f"Next: uv run python scripts/batch_submit.py {jsonl_path}")


if __name__ == "__main__":
    main()
