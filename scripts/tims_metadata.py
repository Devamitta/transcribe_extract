#!/usr/bin/env python3
"""Generates YouTube metadata suggestions (title and description) for Tims Dhamma talks using Gemini API."""

import argparse
import datetime
import re
import time
from pathlib import Path

from tools.provider import generate_content, get_working_key

SYSTEM_INSTRUCTION = """You are preparing YouTube upload metadata for a recorded Dhamma (Buddhist teaching) talk by a senior meditation teacher.

CONTEXT:
- These are intimate Theravāda teaching sessions, not academic lectures.
- The audience is practitioners and people sincerely interested in Buddhist meditation and the Dhamma.
- Sessions often involve Q&A exchanges between the teacher and student(s).
- Pāli terms with proper diacritics (e.g., Nibbāna, Satipaṭṭhāna, Saṅgha, Khandha) are appropriate and preferred — they signal authenticity to the audience. ALWAYS capitalize Pāli terms.
- The video is a static-image upload (no video footage), so the metadata carries all discoverability weight.

TITLE REQUIREMENTS:
- Must capture the central teaching topic of THIS specific talk — not a generic Dhamma title.
- Length: 3–7 words. Be extremely concise and punchy. Avoid connecting words where possible (e.g., use "Valentine's Day, Pema vs Mettā" instead of "Valentine's Day, Pema, and the Practice of Universal Mettā").
- Do NOT use generic openers: "A Talk on...", "Lecture:", "Session:", "Discussion of...", "Exploring...".
- Pāli terms with diacritics are acceptable and preferred when they are the core subject (e.g., "Anicca, Dukkha, Anattā", "The Five Khandhas"). ALWAYS capitalize them.
- The title must be DISTINCTIVE — someone scanning a playlist of 30 talks should immediately understand what this specific talk covers.
- Avoid vague spiritual marketing language: "Deep", "Profound", "Amazing", "Life-Changing".

DESCRIPTION REQUIREMENTS:
- Write exactly 2–3 sentences. No more, no less.
- Sentence 1: State what the teaching covers and why it matters to a practitioner.
- Sentence 2: What the listener will understand, see more clearly, or be able to apply after listening. (Phrases like "You will learn..." are acceptable).
- Sentence 3 (optional but preferred): One notable analogy, framing, or insight from this talk that is distinctive or memorable.
- Tone: clear, grounded, warm — written for a sincere practitioner, not a casual browser.
- Do NOT use marketing language ("Don't miss this!", "Incredible insight!", "You won't believe...").
- Do NOT open every description with "In this talk..." — vary the opening across descriptions.
- Pāli terms are welcome when they are the subject of the talk. ALWAYS capitalize them.
- NEVER mention "A personal story...". Focus entirely on the Dhamma point being illustrated, not the story itself.
- NEVER reference the speaker (e.g., avoid "The teacher explores...", "The speaker discusses..."). Keep descriptions impersonal and focused on the Dhamma.
- EXCEPTION: References to "The Buddha" is excellent and encouraged if mentioned in the talk.

OUTPUT FORMAT:
Respond with EXACTLY two lines. No extra text, no markdown, no explanations before or after.

TITLE: [your suggested title here]
DESCRIPTION: [your suggested description here]
"""


def extract_date_from_filename(filename: str) -> str:
    """Extract YYYY-MM-DD date prefix from a filename, e.g. '2024-11-26 Talk.md' -> '2024-11-26'.
    Returns empty string if no date prefix is found."""
    match = re.match(r"(\d{4}-\d{2}-\d{2})", filename)
    return match.group(1) if match else ""


def generate_metadata(text: str) -> str:
    return generate_content(
        contents=text,
        system_instruction=SYSTEM_INSTRUCTION,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate YouTube metadata suggestions for Tims Dhamma talks."
    )
    parser.add_argument(
        "--input-dir",
        type=str,
        default="output/corrected_pali/tims",
        help="Directory containing transcribed markdown files (default: output/corrected_pali/tims)",
    )
    parser.add_argument(
        "--output-file",
        type=str,
        default="",
        help="The combined review markdown file (default: output/tims_review_YYYY-MM-DD.md)",
    )
    parser.add_argument(
        "--file",
        type=str,
        help="Process only this specific file (test mode)",
    )
    parser.add_argument(
        "--test",
        "-t",
        action="store_true",
        help="Use test models (handled by provider)",
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir)

    if not get_working_key():
        print("All API keys failed. Exiting.")
        return

    if args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            file_path = input_dir / args.file
        if not file_path.exists():
            print(f"File not found: {args.file}")
            return
        md_files = [file_path]
    else:
        if not input_dir.exists():
            print(f"Input directory not found: {input_dir}")
            return
        md_files = sorted(list(input_dir.glob("*.md")))
        if not md_files:
            print(f"No markdown files found in '{input_dir}'.")
            return

    # Determine output date from the LATEST file or today
    date_str = extract_date_from_filename(md_files[-1].name)
    if not date_str:
        date_str = datetime.date.today().isoformat()

    if args.output_file:
        output_file = Path(args.output_file)
    else:
        output_file = Path(f"output/tims_review_{date_str}.md")

    print(f"Found {len(md_files)} files to process.")

    results = []
    total = len(md_files)

    for i, file_path in enumerate(md_files, 1):
        print(f"Processing {i}/{total} '{file_path.name}'...")
        try:
            text = file_path.read_text(encoding="utf-8")
            metadata = generate_metadata(text)

            # Parse metadata
            title = ""
            description = ""
            for line in metadata.strip().split("\n"):
                if line.upper().startswith("TITLE:"):
                    title = line[len("TITLE:") :].strip()
                elif line.upper().startswith("DESCRIPTION:"):
                    description = line[len("DESCRIPTION:") :].strip()

            results.append(
                {
                    "original": file_path.name,
                    "suggested_title": title,
                    "suggested_description": description,
                }
            )

        except Exception as e:
            print(f"  Failed on '{file_path.name}': {e}")

        if len(md_files) > 1:
            print("  Waiting 5s between files...", flush=True)
            time.sleep(5)

    if results:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "# Tims Audio Metadata Review\n",
            "Review and edit the suggested titles and descriptions below.\n",
            "The export script will use this file as the source of truth.\n",
        ]
        for res in results:
            lines.append("\n--- \n")
            lines.append(f"## Source: {res['original']}\n")
            lines.append(f"**Suggested Title:** {res['suggested_title']}\n")
            lines.append(f"**Suggested Description:** {res['suggested_description']}\n")

        output_file.write_text("".join(lines), encoding="utf-8")
        print(f"Review file saved to '{output_file}'.")


if __name__ == "__main__":
    main()
