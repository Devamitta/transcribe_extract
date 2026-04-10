#!/usr/bin/env python3
"""Exports approved Tims Dhamma talk metadata into individual markdown files for YouTube upload descriptions."""

from pathlib import Path
import re
import argparse


def sanitize_filename(filename: str) -> str:
    # Remove characters that are not safe for filenames
    # Replace spaces with underscores or keep them? Let's keep spaces but remove special chars.
    # Actually, often underscores or hyphens are safer.
    # We will remove: \ / : * ? " < > |
    sanitized = re.sub(r'[\\/:*?"<>|]', "", filename)
    # Also strip leading/trailing dots and spaces
    sanitized = sanitized.strip(". ")
    return sanitized


def main():
    parser = argparse.ArgumentParser(
        description="Export approved Tims Dhamma talk metadata."
    )
    parser.add_argument(
        "--review-file",
        type=str,
        default="output/tims_review.md",
        help="Source of truth for approved metadata (default: output/tims_review.md)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="output/audio-tims",
        help="Directory to save approved outputs (default: output/audio-tims)",
    )
    args = parser.parse_args()

    review_file = Path(args.review_file)
    output_dir = Path(args.output_dir)

    if not review_file.exists():
        print(f"Review file not found: {review_file}")
        return

    output_dir.mkdir(parents=True, exist_ok=True)

    with open(review_file, "r", encoding="utf-8") as f:
        content = f.read()

    # Split by separator ---
    sections = re.split(r"\n---", content)

    # The first section is the header
    items = []
    for section in sections[1:]:
        source_match = re.search(r"## Source: (.*)", section)
        title_match = re.search(r"\*\*Approved Title:\*\* (.*)", section)
        desc_match = re.search(r"\*\*Approved Description:\*\* (.*)", section)

        if source_match and title_match and desc_match:
            items.append(
                {
                    "source": source_match.group(1).strip(),
                    "title": title_match.group(1).strip(),
                    "description": desc_match.group(1).strip(),
                }
            )

    if not items:
        print("No approved items found in the review file.")
        return

    print(f"Exporting {len(items)} items...")

    summary_content = "# Tims Audio Export Summary\n\n"

    for item in items:
        sanitized_title = sanitize_filename(item["title"])
        item_output_path = output_dir / f"{sanitized_title}.md"

        item_md = f"# {item['title']}\n\n"
        item_md += "## YouTube Upload Description\n"
        item_md += f"{item['description']}\n\n"
        item_md += "---\n"
        item_md += f"*Source: {item['source']}*\n"

        with open(item_output_path, "w", encoding="utf-8") as f:
            f.write(item_md)

        summary_content += f"## {item['title']}\n"
        summary_content += f"- **Filename:** {sanitized_title}.md\n"
        summary_content += f"- **Description:** {item['description']}\n\n"

    summary_path = output_dir / "summary.md"
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(summary_content)

    print(f"Export complete. Results in '{output_dir}'.")


if __name__ == "__main__":
    main()
