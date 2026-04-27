# Checks OpenAI batch status and writes completed results to output files.

import argparse
import datetime
import json
import sys
from collections import defaultdict
from pathlib import Path

from tools.openai_client import get_batch_status, download_results

OUTPUT_DIRS = {
    "pali": Path("output/corrected_pali"),
    "extract": Path("output/extracted"),
}


def main():
    parser = argparse.ArgumentParser(description="Retrieve OpenAI Batch results.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--batch-id", help="Retrieve specific batch ID")
    group.add_argument(
        "--latest", choices=["pali", "extract"], help="Use latest job for task"
    )
    group.add_argument(
        "--status",
        choices=["pali", "extract"],
        help="Check live status of latest job without downloading",
    )
    group.add_argument(
        "--list", action="store_true", help="List all jobs and their status"
    )

    args = parser.parse_args()

    jobs_path = Path("output/batch_jobs.json")
    if not jobs_path.exists():
        print("No batch jobs found (batch_jobs.json missing).")
        sys.exit(0)

    jobs = json.loads(jobs_path.read_text())

    if args.list:
        for job in jobs:
            print(
                f"[{job['status']:<10}] {job['batch_id']}  {job['task']:<8} {job['submitted_at']}"
            )
        return

    if args.status:
        matching = [j for j in jobs if j["task"] == args.status]
        if not matching:
            print(f"No jobs found for task: {args.status}")
            sys.exit(1)
        check_id = matching[-1]["batch_id"]
        print(f"Checking live status for {args.status} batch {check_id}...")
        try:
            info = get_batch_status(check_id)
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
        counts = info["request_counts"]
        print(f"Status: {info['status']}")
        print(
            f"  total={counts['total']}  completed={counts['completed']}  failed={counts['failed']}"
        )
        if info["status"] == "completed":
            print(
                f"Ready to retrieve: uv run python scripts/batch_retrieve.py --latest {args.status}"
            )
        else:
            print("Not ready yet.")
        return

    batch_id = args.batch_id
    if args.latest:
        matching = [j for j in jobs if j["task"] == args.latest]
        if not matching:
            print(f"No jobs found for task: {args.latest}")
            sys.exit(1)
        # Assuming they are appended in order, pick the last one
        batch_id = matching[-1]["batch_id"]

    # Status check
    print(f"Checking status for batch {batch_id}...")
    try:
        status_info = get_batch_status(batch_id)
    except Exception as e:
        print(f"Error getting status: {e}")
        sys.exit(1)

    print(f"Status: {status_info['status']}")
    counts = status_info["request_counts"]
    print(
        f"  total={counts['total']}  completed={counts['completed']}  failed={counts['failed']}"
    )

    if status_info["status"] == "failed":
        print("Batch failed.")
        sys.exit(1)

    if status_info["status"] != "completed":
        print("Not done yet. Re-run when complete.")
        sys.exit(0)

    # Completed! Download and apply
    print("Downloading results...")
    try:
        results = download_results(batch_id)
    except Exception as e:
        print(f"Error downloading results: {e}")
        sys.exit(1)

    # Group chunks by rel_stem (relative path without extension, e.g. "interview/talk")
    file_chunks: dict[str, list[tuple[int, str]]] = defaultdict(list)

    # We also need to know the task if it wasn't provided via --latest
    job_task = None
    for job in jobs:
        if job["batch_id"] == batch_id:
            job_task = job["task"]
            break

    n_skipped = 0
    for result in results:
        custom_id = result.get("custom_id", "")
        parts = custom_id.split("__")
        if len(parts) != 3:
            print(f"  Warning: bad custom_id {custom_id!r}, skipping")
            n_skipped += 1
            continue

        task_name, rel_stem, chunk_idx_str = parts

        if not job_task:
            job_task = task_name

        resp = result.get("response", {})
        if resp.get("status_code", 200) != 200:
            print(
                f"  Warning: HTTP {resp.get('status_code')} for {custom_id}, skipping"
            )
            n_skipped += 1
            continue

        content = (
            resp.get("body", {})
            .get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        file_chunks[rel_stem].append((int(chunk_idx_str), content))

    # Reconstruct and write files, preserving subdirectory structure
    n_written = 0
    if not job_task or job_task not in OUTPUT_DIRS:
        print(f"Error: Unknown task '{job_task}'. Cannot determine output directory.")
        sys.exit(1)

    out_dir = OUTPUT_DIRS[job_task]

    for rel_stem, chunks in file_chunks.items():
        chunks.sort(key=lambda x: x[0])
        indices = [c[0] for c in chunks]
        expected = list(range(len(chunks)))

        if indices != expected:
            print(
                f"  Warning: chunk gap in {rel_stem}, skipping (got {indices}, expected {expected})"
            )
            n_skipped += 1
            continue

        text = "\n\n".join(c[1] for c in chunks)

        out_path = out_dir / f"{rel_stem}.md"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
        print(f"  Written: {out_path}")
        n_written += 1

    # Update batch_jobs.json
    for job in jobs:
        if job["batch_id"] == batch_id:
            job["status"] = "done"
            job["completed_at"] = datetime.datetime.now().isoformat(timespec="seconds")

    jobs_path.write_text(json.dumps(jobs, indent=2, ensure_ascii=False))

    print(f"\n{n_written} files written, {n_skipped} items skipped.")


if __name__ == "__main__":
    main()
