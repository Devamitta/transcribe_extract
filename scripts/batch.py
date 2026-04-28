# Unified OpenAI Batch API pipeline: prepare, submit, poll, and retrieve in one command.

import argparse
import datetime
import json
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv
from tools.openai_client import (
    prepare_batch_request,
    upload_batch_file,
    create_batch,
    get_batch_status,
    download_results,
)
from tools.pali import (
    get_pali_system_instruction,
    chunk_text_no_overlap,
    get_semantic_eval_instruction,
)
from tools.extract import EXTRACT_SYSTEM_INSTRUCTION, chunk_text
from tools import printer as _p

load_dotenv()

pr = _p.printer

TASK_CONFIG = {
    "pali": {
        "input_dir": Path("output/transcribed"),
        "output_dir": Path("output/corrected_pali"),
        "get_instruction": get_pali_system_instruction,
        "chunk_fn": chunk_text_no_overlap,
        "model_env": "OPENAI_PALI_MODEL",
    },
    "extract": {
        "input_dir": Path("output/corrected_pali"),
        "output_dir": Path("output/extracted"),
        "get_instruction": lambda _: EXTRACT_SYSTEM_INSTRUCTION,
        "chunk_fn": chunk_text,
        "model_env": "OPENAI_EXTRACT_MODEL",
    },
    "semantic": {
        "input_dir": Path("output/corrected_pali"),
        "output_dir": Path("reports/semantic"),
        "get_instruction": lambda _: get_semantic_eval_instruction(),
        "chunk_fn": lambda text: chunk_text_no_overlap(text, chunk_size=5000),
        "model_env": "OPENAI_SEMANTIC_MODEL",
    },
}

OUTPUT_DIRS = {
    "pali": Path("output/corrected_pali"),
    "extract": Path("output/extracted"),
    "semantic": Path("reports/semantic"),
}

JOBS_PATH = Path("output/batch_jobs.json")


def _apply_pali_corrections(original: str, json_response: str) -> str:
    """Apply JSON correction array from OpenAI to original chunk text."""
    try:
        j = json_response.strip()
        if j.startswith("```json"):
            j = j[7:].strip()
        if j.endswith("```"):
            j = j[:-3].strip()
        corrections = json.loads(j)
        text = original
        for item in corrections:
            if (
                not isinstance(item, dict)
                or "original" not in item
                or "corrected" not in item
            ):
                continue
            pattern = re.compile(
                rf"\b{re.escape(str(item['original']))}\b", re.IGNORECASE
            )
            text = pattern.sub(str(item["corrected"]), text)
        return text
    except Exception as e:
        pr.warning(f"Correction parse failed: {e} — keeping original")
        return original


def prepare(task: str, folder: str | None, limit: int | None) -> Path | None:
    """Prepare JSONL; return path or None if nothing to queue."""
    config = TASK_CONFIG[task]

    if folder:
        path = config["input_dir"] / folder
        if not path.exists():
            pr.error(f"Folder not found: {folder}")
            sys.exit(1)
        md_files = sorted(list(path.rglob("*.md")))
    else:
        md_files = sorted(list(config["input_dir"].rglob("*.md")))

    if not md_files:
        pr.amber(f"No .md files found for task '{task}'.")
        return None

    model = os.getenv(config["model_env"], "gpt-4o-mini")
    queue = []
    skipped = 0

    for file_path in md_files:
        try:
            rel = file_path.relative_to(config["input_dir"])
            output_path = config["output_dir"] / rel
        except ValueError:
            output_path = config["output_dir"] / file_path.name
        output_path_flat = config["output_dir"] / file_path.name

        if output_path.exists() or output_path_flat.exists():
            pr.amber(f"[SKIP] {file_path.name}")
            skipped += 1
        else:
            pr.green(f"[QUEUE] {file_path.name}")
            queue.append(file_path)

    pr.info(f"{skipped} already done, {len(queue)} to process")

    if limit and len(queue) > limit:
        pr.info(f"Limiting to first {limit} files (--limit).")
        queue = queue[:limit]

    if not queue:
        pr.info("Nothing to prepare.")
        return None

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
                pr.warning(f"path contains '__' delimiter: {file_path}")
            text = file_path.read_text(encoding="utf-8")
            chunks = config["chunk_fn"](text)

            # Dynamically get instruction based on file_path (for folder-aware glossary)
            system_instruction = config["get_instruction"](file_path)

            for i, chunk in enumerate(chunks):
                custom_id = f"{task}__{rel_stem}__{i:04d}"
                record = prepare_batch_request(
                    custom_id, system_instruction, chunk, model
                )
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                total_chunks += 1

    pr.info(f"Written {total_chunks} requests to {jsonl_path}")
    pr.info(f"Files: {len(queue)}  Model: {model}")
    return jsonl_path


def submit(jsonl_path: Path, task: str) -> str:
    """Upload and create batch; return batch_id."""
    with open(jsonl_path, "r", encoding="utf-8") as f:
        count = sum(1 for _ in f)

    pr.green_tmr(f"Submitting {count} requests...")
    file_id = upload_batch_file(jsonl_path)
    pr.yes(f"file {file_id}")

    pr.green_tmr("Creating batch...")
    batch_id = create_batch(file_id)
    pr.yes(f"batch {batch_id}")

    jobs = json.loads(JOBS_PATH.read_text()) if JOBS_PATH.exists() else []
    jobs.append(
        {
            "batch_id": batch_id,
            "task": task,
            "jsonl_path": str(jsonl_path),
            "submitted_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "status": "submitted",
        }
    )

    JOBS_PATH.parent.mkdir(exist_ok=True, parents=True)
    JOBS_PATH.write_text(json.dumps(jobs, indent=2, ensure_ascii=False))

    return batch_id


def poll_until_done(batch_id: str, task: str, poll_interval: int) -> bool:
    """Poll until completed or failed. Return True if completed."""
    pr.green(f"Polling every {poll_interval}s")
    pr.amber("Ctrl+C to stop and retrieve manually later")

    try:
        while True:
            info = get_batch_status(batch_id)
            status = info["status"]
            counts = info["request_counts"]
            ts = datetime.datetime.now().strftime("%H:%M:%S")

            if status == "completed":
                pr.cyan(f"[{ts}] {status} — {counts['completed']}/{counts['total']}")
                return True

            if status in ("failed", "cancelled", "expired"):
                pr.error(f"Batch {status}.")
                return False

            pr.cyan(f"[{ts}] {status} — {counts['completed']}/{counts['total']}")
            time.sleep(poll_interval)

    except KeyboardInterrupt:
        pr.amber("\nInterrupted. Batch still running.")
        pr.amber(f"Resume: uv run python scripts/batch.py --status {task}")
        return False


def retrieve(batch_id: str) -> None:
    """Download results and write output files."""
    jobs = json.loads(JOBS_PATH.read_text())
    job = next((j for j in jobs if j["batch_id"] == batch_id), None)
    job_task = job["task"] if job else None
    jsonl_path = Path(job["jsonl_path"]) if job else None

    # For pali: load original chunk texts from the JSONL input so we can apply corrections
    original_chunks: dict[str, str] = {}
    if job_task == "pali" and jsonl_path and jsonl_path.exists():
        with open(jsonl_path, encoding="utf-8") as f:
            for line in f:
                req = json.loads(line)
                original_chunks[req["custom_id"]] = req["body"]["messages"][1][
                    "content"
                ]

    pr.green_tmr("Downloading results...")
    results = download_results(batch_id)
    pr.yes("downloaded")

    # Store (chunk_idx, content, custom_id) per file
    file_chunks: dict[str, list[tuple[int, str, str]]] = defaultdict(list)

    n_skipped = 0
    for result in results:
        custom_id = result.get("custom_id", "")
        parts = custom_id.split("__")
        if len(parts) != 3:
            pr.warning(f"bad custom_id {custom_id!r}, skipping")
            n_skipped += 1
            continue

        task_name, rel_stem, chunk_idx_str = parts

        if not job_task:
            job_task = task_name

        resp = result.get("response", {})
        if resp.get("status_code", 200) != 200:
            pr.warning(f"HTTP {resp.get('status_code')} for {custom_id}")
            n_skipped += 1
            continue

        content = (
            resp.get("body", {})
            .get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        file_chunks[rel_stem].append((int(chunk_idx_str), content, custom_id))

    if not job_task or job_task not in OUTPUT_DIRS:
        pr.error(f"Unknown task '{job_task}'. Cannot determine output directory.")
        sys.exit(1)

    out_dir = OUTPUT_DIRS[job_task]
    n_written = 0

    for rel_stem, chunks in file_chunks.items():
        chunks.sort(key=lambda x: x[0])
        indices = [c[0] for c in chunks]
        expected = list(range(len(chunks)))

        if indices != expected:
            pr.warning(
                f"chunk gap in {rel_stem}, skipping (got {indices}, expected {expected})"
            )
            n_skipped += 1
            continue

        if job_task == "pali":
            # Apply JSON corrections to original chunk text
            corrected = []
            for _, json_response, cid in chunks:
                original = original_chunks.get(cid, "")
                corrected.append(_apply_pali_corrections(original, json_response))
            text = "\n\n".join(corrected)
        elif job_task == "extract":
            text = "\n\n".join(c[1] for c in chunks)
        elif job_task == "semantic":
            findings = []
            for _, json_response, cid in chunks:
                try:
                    j = json_response.strip()
                    if j.startswith("```json"):
                        j = j[7:].strip()
                    if j.endswith("```"):
                        j = j[:-3].strip()
                    items = json.loads(j)
                    if isinstance(items, list):
                        findings.extend(items)
                except Exception as e:
                    pr.warning(f"Semantic parse failed for {cid}: {e}")
            text = f"# Semantic Evaluation: {rel_stem}\n\n"
            if findings:
                for item in findings:
                    text += f"## Passage\n> {item.get('passage', '')}\n\n"
                    text += f"**Issue:** {item.get('issue', '')}\n\n"
                    text += f"**Suggestion:** {item.get('suggestion', '')}\n\n---\n\n"
            else:
                text += "_No anomalies detected._\n"

        out_path = out_dir / f"{rel_stem}.md"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
        pr.green(f"  Written: {out_path}")
        n_written += 1

    jobs = json.loads(JOBS_PATH.read_text())
    for job in jobs:
        if job["batch_id"] == batch_id:
            job["status"] = "done"
            job["completed_at"] = datetime.datetime.now().isoformat(timespec="seconds")
            break

    JOBS_PATH.write_text(json.dumps(jobs, indent=2, ensure_ascii=False))
    pr.yes(f"{n_written} files written")
    if n_skipped:
        pr.no(f"{n_skipped} items skipped")


def show_status(task: str | None) -> None:
    """Check and display status of latest batch for task."""
    jobs = json.loads(JOBS_PATH.read_text()) if JOBS_PATH.exists() else []

    if not jobs:
        pr.info("No batches tracked yet.")
        return

    if task:
        matching = [j for j in jobs if j["task"] == task]
        if not matching:
            pr.info(f"No jobs found for task: {task}")
            return
        batch_id = matching[-1]["batch_id"]
    else:
        batch_id = jobs[-1]["batch_id"]

    pr.green_tmr(f"Checking status for {batch_id}...")
    try:
        info = get_batch_status(batch_id)
    except Exception as e:
        pr.error(f"Error: {e}")
        sys.exit(1)

    counts = info["request_counts"]
    pr.info(f"Status: {info['status']}")
    pr.info(
        f"  total={counts['total']}  completed={counts['completed']}  failed={counts['failed']}"
    )

    if info["status"] == "completed":
        pr.green("Ready to retrieve: uv run python scripts/batch.py --retrieve")


def show_list() -> None:
    """List all tracked jobs."""
    jobs = json.loads(JOBS_PATH.read_text()) if JOBS_PATH.exists() else []

    if not jobs:
        pr.info("No batches tracked yet.")
        return

    pr.info("Batch jobs:")
    for job in jobs:
        print(
            f"[{job['status']:<10}] {job['batch_id']}  {job['task']:<8} {job['submitted_at']}"
        )


def run_stage(
    task: str, folder: str | None, limit: int | None, poll_interval: int, no_wait: bool
) -> None:
    """Run one stage: prepare → submit → (poll → retrieve)."""
    pr.title(f"Stage: {task}")

    jsonl = prepare(task, folder, limit)
    if not jsonl:
        return

    batch_id = submit(jsonl, task)

    if no_wait:
        pr.amber(
            f"--no-wait: batch submitted. Check status: uv run python scripts/batch.py --status {task}"
        )
        return

    if not poll_until_done(batch_id, task, poll_interval):
        sys.exit(1)

    retrieve(batch_id)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Unified OpenAI Batch API pipeline: prepare, submit, poll, retrieve."
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument("--status", nargs="?", const="latest", help="Check batch status")
    group.add_argument("--list", action="store_true", help="List all tracked jobs")

    parser.add_argument(
        "--stage",
        choices=["pali", "extract", "semantic", "both"],
        default="both",
        help="Which stage to run (default: both)",
    )
    parser.add_argument("--folder", help="Limit to specific subfolder (e.g. interview)")
    parser.add_argument("--limit", type=int, help="Limit to first N files")
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=30,
        help="Poll interval in seconds (default: 30)",
    )
    parser.add_argument(
        "--no-wait", action="store_true", help="Submit only, don't wait for completion"
    )

    args = parser.parse_args()

    if args.status is not None:
        if args.status == "latest":
            show_status(None)
        else:
            show_status(args.status)
    elif args.list:
        show_list()
    else:
        stages = ["pali", "extract"] if args.stage == "both" else [args.stage]
        for stage in stages:
            run_stage(stage, args.folder, args.limit, args.poll_interval, args.no_wait)


if __name__ == "__main__":
    main()
