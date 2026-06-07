"""Generates AI thumbnail images for Dhamma talks using OpenRouter FLUX."""

import argparse
import re
from pathlib import Path

from tools.dry_run import create_stub, is_pipeline_dry_run
from tools.image_gen import generate_image
from tools.printer import printer as pr
from tools.provider import generate_content, get_working_key
from tools.source_scope import read_source_filter, source_matches_filter
from tools.uploader_common import is_uploaded_in_history, load_nested_history


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

LANG_TO_FOLDER: dict[str, str] = {"ru": "russian", "en": "english"}
HISTORY_PATH = Path("output/youtube_history.json")


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
            talk["source"] = Path(source_full).stem

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


def build_prompt(title: str, description: str, lang: str) -> str:
    """Ask LLM to generate a specific, evocative image prompt from the talk content."""
    pr.amber(f"    Building prompt for: {title}")

    contents = f"Title: {title}\nDescription: {description}"

    try:
        prompt = generate_content(contents, SYSTEM_INSTRUCTIONS[lang]).strip()
        prompt = re.sub(r'^["\']|["\']$', "", prompt)
    except Exception as e:
        pr.amber(f"    Prompt generation failed: {e}. Using fallback.")
        prompt = (
            "A serene Theravada forest monastery at dawn, ancient stone architecture, "
            "tropical trees, morning mist, soft golden light. "
            "No people, no text, photorealistic, cinematic."
        )

    return prompt


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate AI thumbnail images.")
    parser.add_argument(
        "--lang",
        type=str,
        required=True,
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
        return

    if not args.dry_run and not get_working_key():
        pr.no("All API keys failed. Exiting.")
        return

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
        return

    history = load_nested_history(HISTORY_PATH, args.lang)
    if not args.force:
        all_talks = [
            item
            for item in all_talks
            if not is_uploaded_in_history(history, f"{item[2]['source']}.mp4")
        ]

    if not all_talks:
        pr.green("All approved talks are already uploaded.")
        return

    # Pass 2: process
    existing = sum(
        1
        for _, od, t in all_talks
        if (
            od / f"{t.get('source', sanitize_filename(t.get('title', 'Untitled')))}.jpg"
        ).exists()
        and not args.show_prompts
    )
    new_count = len(all_talks) - existing
    pr.green_title(
        f"Generating thumbnails for {new_count} of {len(all_talks)} talks ({existing} already exist)..."
    )
    created, skipped, errors = 0, 0, 0

    for folder_name, output_dir, talk in all_talks:
        output_dir.mkdir(parents=True, exist_ok=True)

        title = talk.get("title", "Untitled")
        description = talk.get("description", "")
        source = talk.get("source", sanitize_filename(title))
        out_path = output_dir / f"{source}.jpg"

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
            prompt = build_prompt(title, description, args.lang)
            pr.cyan(f"\n--- {title} ---")
            pr.white(prompt)
            continue

        pr.green(f"  [{folder_name}] {title}")
        prompt = build_prompt(title, description, args.lang)
        pr.green(f"    → {prompt[:100]}...")

        try:
            generate_image(prompt, out_path)
            if args.created_log:
                with open(args.created_log, "a") as log_f:
                    log_f.write(str(out_path) + "\n")
            pr.yes(f"    Created: {out_path.name}")
            created += 1
        except Exception as e:
            pr.no(f"    Failed: {title}")
            pr.amber(f"    {e}")
            errors += 1

    pr.yes(f"Done: {created} created, {skipped} skipped, {errors} errors")


if __name__ == "__main__":
    main()
