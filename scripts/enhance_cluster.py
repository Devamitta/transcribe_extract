#!/usr/bin/env python3
"""Cluster enhance backlog items via direct LLM API call (replaces subagent delegation)."""

import argparse
import concurrent.futures
import json
import sys
from pathlib import Path

from tools import printer
from tools.provider import build_cacheable_contents, generate_with_timeout


class ClusteringError(RuntimeError):
    """Raised when clustering cannot be completed safely."""


def build_cluster_instruction() -> str:
    return (
        "You are an expert software project manager. Your task is to group the "
        "enhance backlog items below into logical clusters by theme or root cause.\n\n"
        "RULES:\n"
        "- Each item should belong to exactly one cluster.\n"
        "- Cluster labels should be concise (1-5 words) and descriptive.\n"
        "- Items within a cluster should share a common theme (e.g. 'over-compression', "
        "'formatting issues', 'Pali terminology').\n\n"
        "OUTPUT: Return ONLY a valid JSON array. Each item must have exactly these keys:\n"
        '  {"cluster_label": "short label", "items": ["bullet 1", "bullet 2", ...]}\n'
        "No other text outside the JSON."
    )


def cluster_backlog(backlog_text: str) -> list[dict[str, object]]:
    if not backlog_text.strip():
        return []

    instruction = build_cluster_instruction()
    try:
        result = generate_with_timeout(
            contents=build_cacheable_contents(backlog_text),
            system_instruction=instruction,
        )
        if not result or not result.strip():
            raise ClusteringError("empty response from LLM")

        json_str = result.strip()
        if json_str.startswith("```json"):
            json_str = json_str[7:].strip()
        if json_str.endswith("```"):
            json_str = json_str[:-3].strip()

        items = json.loads(json_str)
    except ClusteringError:
        raise
    except concurrent.futures.TimeoutError as exc:
        raise ClusteringError("timeout") from exc
    except json.JSONDecodeError as exc:
        raise ClusteringError(f"invalid JSON: {exc}") from exc
    except Exception as exc:
        raise ClusteringError(f"request failed: {exc}") from exc

    if not isinstance(items, list):
        raise ClusteringError("clustering response JSON was not a list")

    clusters: list[dict[str, object]] = []
    for item in items:
        if not isinstance(item, dict):
            raise ClusteringError("clustering response item was not an object")
        clusters.append(item)

    return clusters


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Cluster enhance backlog items via LLM."
    )
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "backlog_file", nargs="?", help="Path to backlog text file."
    )
    input_group.add_argument(
        "--stdin", action="store_true", help="Read backlog from stdin."
    )

    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    if args.stdin:
        backlog = sys.stdin.read()
    else:
        backlog = Path(args.backlog_file).read_text(encoding="utf-8")

    try:
        clusters = cluster_backlog(backlog)
    except ClusteringError as exc:
        pr = printer.printer
        pr.no(f"Clustering failed: {exc}")
        return 1

    print(json.dumps(clusters, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
