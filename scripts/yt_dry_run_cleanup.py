"""Removes [DRY_RUN] stub entries from the review file after a pipeline dry-run completes."""

import argparse
import re
from pathlib import Path

from tools.lang import LANG_TO_FOLDER
from tools.printer import printer as pr


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Strip [DRY_RUN] entries from the review file."
    )
    parser.add_argument("--lang", default="en", choices=["ru", "en"])
    args = parser.parse_args()

    lang_folder = LANG_TO_FOLDER[args.lang]
    review_path = Path("reviews") / f"{lang_folder}_review.md"

    if not review_path.exists():
        return

    content = review_path.read_text(encoding="utf-8")
    sections = re.split(r"\n---", content)

    filtered = [s for s in sections if "[DRY_RUN]" not in s]

    removed = len(sections) - len(filtered)
    if removed == 0:
        return

    pr.green(f"Removing {removed} dry-run stub(s) from {review_path}")
    pr.bip()
    review_path.write_text("\n---".join(filtered), encoding="utf-8")
    pr.yes(f"Removed {removed} stub section(s)")


if __name__ == "__main__":
    main()
