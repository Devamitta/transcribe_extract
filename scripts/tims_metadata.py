import sys
from pathlib import Path
import time
import argparse

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.provider import generate_content, get_working_key

SYSTEM_INSTRUCTION = """You are creating YouTube metadata for a Dhamma talk transcript.

TASK: Suggest a clear, engaging title and a concise YouTube upload description for a static-image video upload.

OUTPUT FORMAT:
- Title: A concise, catchy but respectful title for the Dhamma talk. Keep it filename-safe.
- Description: A 1-2 sentence summary of the teaching that invites the viewer to listen.

Structure your response EXACTLY like this:
TITLE: [suggested title]
DESCRIPTION: [suggested description]
"""


def generate_metadata(text: str) -> str:
    return generate_content(
        contents=text,
        system_instruction=SYSTEM_INSTRUCTION,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Generate YouTube metadata suggestions for Tims Dhamma talks."
    )
    parser.add_argument(
        "--input-dir",
        type=str,
        default="output/transcribed/tims",
        help="Directory containing transcribed markdown files (default: output/transcribed/tims)",
    )
    parser.add_argument(
        "--output-file",
        type=str,
        default="output/tims_review.md",
        help="The combined review markdown file (default: output/tims_review.md)",
    )
    parser.add_argument(
        "--file",
        type=str,
        help="Process only this specific file (test mode)",
    )
    parser.add_argument(
        "--test", "-t",
        action="store_true",
        help="Use test models (handled by provider)",
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_file = Path(args.output_file)

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

    print(f"Found {len(md_files)} files to process.")

    results = []
    # If output file exists, we might want to append or just overwrite for now as per "one combined markdown review file"
    # Actually, the spec says "one combined markdown review file that lists, for every source file..."

    for file_path in md_files:
        print(f"Processing '{file_path.name}'...")
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()

        try:
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

        print("  Waiting 5s between files...", flush=True)
        time.sleep(5)

    if results:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("# Tims Audio Metadata Review\n\n")
            f.write("Review and edit the suggested titles and descriptions below.\n")
            f.write("The export script will use this file as the source of truth.\n\n")
            for res in results:
                f.write("--- \n")
                f.write(f"## Source: {res['original']}\n")
                f.write(f"**Approved Title:** {res['suggested_title']}\n")
                f.write(f"**Approved Description:** {res['suggested_description']}\n\n")
        print(f"Review file saved to '{output_file}'.")


if __name__ == "__main__":
    main()
