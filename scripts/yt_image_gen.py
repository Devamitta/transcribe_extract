"""Generates AI thumbnail images for Dhamma talks using OpenRouter FLUX."""

import argparse
import json
import re
import unicodedata
from pathlib import Path

from tools.dry_run import create_stub, is_pipeline_dry_run
from tools.image_gen import generate_image
from tools.lang import LANG_TO_FOLDER
from tools.printer import printer as pr
from tools.provider import generate_content
from tools.source_scope import read_source_filter, source_matches_filter
from tools.uploader_common import (
    find_path_by_normalized_name,
    is_uploaded_in_history,
    load_nested_history,
)
from tools.yt_chapters_retry import LLMRetryError, retry_llm_request


SYSTEM_INSTRUCTIONS: dict[str, str] = {
    "ru": """You are a YouTube thumbnail art director for a Theravada Buddhist monk's Dhamma talk channel. Given a talk title and description in Russian, write a single detailed English image generation prompt for a photorealistic 16:9 thumbnail.

HOW TO DERIVE THE SCENE:
Read the description carefully. It is your only source material — do not use generic Buddhist imagery that could apply to any talk. Instead:
1. Look for any concrete object, comparison, or analogy in the description (a simile the teacher uses, a physical thing mentioned, a specific scene described). If you find one, build the entire image around it. That object or scene, rendered in a monastery setting, IS the thumbnail.
2. If the description contains no concrete object, identify the central theme and ask: what single physical thing in a monastery or forest setting UNIQUELY embodies this specific talk's teaching — something that could not serve as a thumbnail for any other talk? Use that.

Style: Peaceful, dignified, suitable for a Buddhist monastic channel. Setting: Theravada forest monastery or Southeast Asian nature. Lighting: soft morning light, golden hour, or candlelight. Photorealistic, cinematic, 8K detail.

HARD CONSTRAINTS (never violate): zero people, zero monks, zero human figures or body parts. Zero text, letters, signs, or writing anywhere in the scene.
Output: one paragraph only, no preamble, no labels, no quotes.
""",
    "en": """You are a YouTube thumbnail art director for a Theravada Buddhist monk's Dhamma talk channel. Given a talk title and description in English, write a single detailed English image generation prompt for a photorealistic 16:9 thumbnail.

HOW TO DERIVE THE SCENE:
Read the description carefully. It is your only source material — do not use generic Buddhist imagery that could apply to any talk. Instead:
1. Look for any concrete object, comparison, or analogy in the description (a simile the teacher uses, a physical thing mentioned, a specific scene described). If you find one, build the entire image around it. That object or scene, rendered in a monastery setting, IS the thumbnail.
2. If the description contains no concrete object, identify the central theme and ask: what single physical thing in a monastery or forest setting UNIQUELY embodies this specific talk's teaching — something that could not serve as a thumbnail for any other talk? Use that.

Style: Peaceful, dignified, suitable for a Buddhist monastic channel. Setting: Theravada forest monastery or Southeast Asian nature. Lighting: soft morning light, golden hour, or candlelight. Photorealistic, cinematic, 8K detail.

HARD CONSTRAINTS (never violate): zero people, zero monks, zero human figures or body parts. Zero text, letters, signs, or writing anywhere in the scene.
Output: one paragraph only, no preamble, no labels, no quotes.
""",
}

HISTORY_PATH = Path("output/youtube_history.json")
SUBJECTS_LOG_PATH = Path("output/thumbnail_subjects.json")
MAX_LLM_ATTEMPTS = 3
LLM_RETRY_DELAY_S = 3.0


def sanitize_filename(name: str) -> str:
    """Sanitize filename by removing invalid characters."""
    return re.sub(r'[\\/:*?"<>|]', "", name).strip(". ")


def parse_review(review_path: Path) -> list[dict[str, str]]:
    """Parse the review markdown file for approved talks with recording dates."""
    content = review_path.read_text(encoding="utf-8")
    sections = content.split("\n---")
    talks = []

    for section in sections:
        section = section.strip()
        if not section or "Source:" not in section:
            continue

        talk = {}

        # Source line
        source_match = re.search(r"Source:\s*(.+)", section)
        if source_match:
            source_full = source_match.group(1).strip()
            talk["source"] = unicodedata.normalize("NFC", Path(source_full).stem)

        # Title
        title_match = re.search(r"\*\*Suggested Title:\*\*\s*(.+)", section)
        if title_match:
            talk["title"] = title_match.group(1).strip()

        # Approved field
        approved_m = re.search(r"\*\*Approved:\*\*\s*(yes|no)", section, re.IGNORECASE)
        talk["approved"] = approved_m.group(1).lower() == "yes" if approved_m else False

        # Recording Date (DD-MM-YYYY)
        date_match = re.search(r"\*\*Recording Date:\*\*\s*([\d-]+)", section)
        if date_match:
            talk["recording_date"] = date_match.group(1).strip()

        # Description
        desc_match = re.search(
            r"\*\*Suggested Description:\*\*\s*(.*)", section, re.DOTALL
        )
        if desc_match:
            desc_text = desc_match.group(1).strip()
            desc_lines = []
            for line in desc_text.splitlines():
                if (
                    line.startswith("**")
                    or line.startswith("##")
                    or line.startswith("---")
                ):
                    break
                desc_lines.append(line)
            talk["description"] = "\n".join(desc_lines).strip()

        if "title" in talk and talk.get("recording_date") and talk.get("approved"):
            talks.append(talk)

    return talks


def _load_subjects() -> list[dict[str, str]]:
    """Load existing thumbnail subjects from the rolling log."""
    if not SUBJECTS_LOG_PATH.exists():
        return []
    try:
        data: dict[str, object] = json.loads(
            SUBJECTS_LOG_PATH.read_text(encoding="utf-8")
        )
        subjects = data.get("subjects", [])
        return subjects if isinstance(subjects, list) else []
    except (json.JSONDecodeError, KeyError, TypeError):
        return []


def _save_subject(file_name: str, subject: str) -> None:
    """Append a subject entry to the log."""
    subjects = _load_subjects()
    subjects = [s for s in subjects if s.get("file") != file_name]
    subjects.append({"file": file_name, "subject": subject})
    SUBJECTS_LOG_PATH.write_text(
        json.dumps({"subjects": subjects}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _extract_subject(prompt: str) -> str:
    """Summarise the main visual subject of an image prompt in 3-6 words."""
    result = generate_content(
        f"In 3-6 words, what is the single main visual subject of this image description?\n\n{prompt[:400]}",
        "Be extremely concise. Output only 3-6 words describing the dominant object or scene element. No punctuation, no explanation.",
    )
    return result.strip()


def build_prompt(title: str, description: str, lang: str) -> str:
    """Ask LLM to generate a specific, evocative image prompt from the talk content."""
    pr.amber(f"    Building prompt for: {title}")

    subjects = _load_subjects()
    avoid_subjects = [s["subject"] for s in subjects]
    avoid_clause = ""
    if avoid_subjects:
        avoid_clause = (
            "\n\nPREVIOUSLY USED SUBJECTS — do NOT repeat any of these or close visual variants:\n"
            + "\n".join(f"- {s}" for s in avoid_subjects)
        )

    contents = f"Title: {title}\nDescription: {description}"
    prompt = generate_content(
        contents, SYSTEM_INSTRUCTIONS[lang] + avoid_clause
    ).strip()
    return re.sub(r'^["\']|["\']$', "", prompt)


def generate_image_with_retry(prompt: str, out_path: Path, source_name: str) -> None:
    """Generate one required thumbnail image, retrying provider failures."""
    retry_llm_request(
        lambda _attempt: _generate_image_response(prompt, out_path),
        file_name=source_name,
        action="image generation",
        max_attempts=MAX_LLM_ATTEMPTS,
        retry_delay_s=LLM_RETRY_DELAY_S,
    )


def _generate_image_response(prompt: str, out_path: Path) -> str:
    try:
        generate_image(prompt, out_path)
    except Exception:
        if out_path.exists():
            out_path.unlink()
        raise
    return "created"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate AI thumbnail images.")
    parser.add_argument(
        "--lang",
        type=str,
        default="en",
        choices=["ru", "en"],
        help="Language of the talk (ru|en).",
    )
    parser.add_argument(
        "--folder",
        type=str,
        help="Subfolder name (e.g. 'russian'). Defaults to lang-based folder (ru→russian, en→english).",
    )
    parser.add_argument("--review-file", type=Path, help="Path to specific review file")
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Output directory for images",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't generate images, just show what would be done",
    )
    parser.add_argument(
        "--show-prompts",
        action="store_true",
        help="Re-generate and print full image prompts for all talks, no image API calls",
    )
    parser.add_argument(
        "--test", "-t", action="store_true", help="Use test LLM models."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Process only the first N talks (0=unlimited).",
    )
    parser.add_argument(
        "--created-log",
        type=str,
        default=None,
        help="Path to a file where created image paths are appended (one per line).",
    )
    parser.add_argument(
        "--source-log",
        type=Path,
        help="Only process review sources listed in this log.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Generate images even when YouTube history marks videos uploaded.",
    )

    args = parser.parse_args()
    source_filter = read_source_filter(args.source_log)

    if args.folder is not None:
        folder_names = [args.folder]
    else:
        folder_names = [LANG_TO_FOLDER[args.lang]]

    if not folder_names:
        pr.no("No subfolders found in 'output/transcribed/'.")
        return 0

    # Pass 1: collect all approved talks from all folders
    all_talks: list[tuple[str, Path, dict]] = []
    lang_folder = LANG_TO_FOLDER.get(args.lang, "english")
    for folder_name in folder_names:
        output_dir = args.output_dir or Path("output/thumbnails") / folder_name
        review_path = args.review_file or Path("reviews") / f"{lang_folder}_review.md"

        if not review_path or not review_path.exists():
            if args.folder:
                pr.no(f"  Review file not found at '{review_path}'.")
            continue

        talks = parse_review(review_path)
        if not talks:
            continue

        for talk in talks:
            if not source_matches_filter(talk.get("source", ""), source_filter):
                continue
            all_talks.append((folder_name, output_dir, talk))

    # Apply global limit
    if args.limit > 0:
        all_talks = all_talks[: args.limit]

    if not all_talks:
        pr.no("No approved talks found to process.")
        return 0

    history = load_nested_history(HISTORY_PATH, args.lang)
    if not args.force:
        all_talks = [
            item
            for item in all_talks
            if not is_uploaded_in_history(history, f"{item[2]['source']}.mp4")
        ]

    if not all_talks:
        pr.green("All approved talks are already uploaded.")
        return 0

    pending_talks: list[tuple[str, Path, dict]] = []
    existing = 0
    for item in all_talks:
        _, output_dir, talk = item
        source = talk.get("source", sanitize_filename(talk.get("title", "Untitled")))
        out_path = find_path_by_normalized_name(output_dir, f"{source}.jpg")
        if out_path.exists() and not args.show_prompts:
            existing += 1
            continue
        pending_talks.append(item)

    if not pending_talks:
        pr.green("Nothing to do.")
        return 0

    # Pass 2: process
    new_count = len(pending_talks)
    pr.green_title(
        f"Generating thumbnails for {new_count} of {len(all_talks)} talks ({existing} already exist)..."
    )
    created, skipped, errors = 0, 0, 0

    for folder_name, output_dir, talk in pending_talks:
        output_dir.mkdir(parents=True, exist_ok=True)

        title = talk.get("title", "Untitled")
        description = talk.get("description", "")
        source = talk.get("source", sanitize_filename(title))
        out_path = find_path_by_normalized_name(output_dir, f"{source}.jpg")

        if out_path.exists() and not args.show_prompts:
            skipped += 1
            continue

        if args.dry_run:
            review_path_used = (
                args.review_file
                or Path("reviews")
                / f"{LANG_TO_FOLDER.get(args.lang, 'english')}_review.md"
            )
            pr.white(f"  [DRY RUN] {review_path_used} → {out_path}")
            if is_pipeline_dry_run():
                create_stub(out_path)
            continue

        if args.show_prompts:
            try:
                prompt = retry_llm_request(
                    lambda _attempt: build_prompt(title, description, args.lang),
                    file_name=source,
                    action="thumbnail prompt generation",
                    max_attempts=MAX_LLM_ATTEMPTS,
                    retry_delay_s=LLM_RETRY_DELAY_S,
                )
                pr.cyan(f"\n--- {title} ---")
                pr.white(prompt)
            except LLMRetryError as e:
                pr.no(f"    Failed: {title}")
                pr.amber(f"    {e}")
                errors += 1
            continue

        pr.green(f"  [{folder_name}] {title}")

        try:
            prompt = retry_llm_request(
                lambda _attempt: build_prompt(title, description, args.lang),
                file_name=source,
                action="thumbnail prompt generation",
                max_attempts=MAX_LLM_ATTEMPTS,
                retry_delay_s=LLM_RETRY_DELAY_S,
            )
            pr.green(f"    → {prompt[:100]}...")
            generate_image_with_retry(prompt, out_path, source)
            try:
                subject = _extract_subject(prompt)
                _save_subject(f"{source}.jpg", subject)
            except Exception:
                pass  # subject tracking is best-effort
            if args.created_log:
                with open(args.created_log, "a", encoding="utf-8") as log_f:
                    log_f.write(str(out_path) + "\n")
            pr.yes(f"    Created: {out_path.name}")
            created += 1
        except LLMRetryError as e:
            pr.no(f"    Failed: {title}")
            pr.amber(f"    {e}")
            errors += 1
        except Exception as e:
            pr.no(f"    Failed: {title}")
            pr.amber(f"    {e}")
            errors += 1

    pr.yes(f"Done: {created} created, {skipped} skipped, {errors} errors")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
