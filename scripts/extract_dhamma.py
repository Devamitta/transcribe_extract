import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pathlib import Path
import time

from tools.provider import generate_content, get_working_key

CHUNK_SIZE = 2000
CHUNK_OVERLAP = 500

SYSTEM_INSTRUCTION = (
    "You are a strict text editor preparing a raw transcript for a database. Your task is selective redaction, not summarization.\n"
    "\n"
    "Read the provided chunk of a teacher-student dialog.\n"
    "\n"
    "DELETE all casual pleasantries, logistical planning, personal background information, and off-topic deviations.\n"
    "\n"
    "RETAIN all Dhamma discussions, philosophical points, examples, metaphors, and specific student questions followed by teacher answers.\n"
    "\n"
    "DO NOT SUMMARIZE. You must preserve the detailed explanations, analogies, and original phrasing of the Dhamma concepts exactly as they were spoken.\n"
    "\n"
    "If a student makes an incorrect claim that is corrected by the teacher, keep both the question and the correction to preserve the context of the learning.\n"
    "\n"
    "Output the cleaned text in readable paragraphs. If the entire chunk is off-topic personal logistics, output exactly 'NO_DHAMMA'.\n"
    "\n"
    "CRITICAL: Do not use the words 'extract' or 'summarize' in your output.\n"
    "\n"
    "Now output as a clean Markdown bulleted list. Each bullet point MUST include a topic tag in brackets at the start,\n"
    "   e.g. '[kamma] The law of kamma explains that actions have consequences...'\n"
    "Use these tags when relevant: [kamma], [satipaṭṭhāna], [jhāna], [mettā], [dukkha], [nibbāna], [sīla], [samādhi], [paññā], [four-noble-truths], [noble-eightfold-path], [seven-factors], [brahmavihāra], [anattā], [khandha], [upekkhā], [asubha].\n"
    "If a point doesn't fit any specific tag, use [general].\n"
    "If no Dhamma points exist in this transcript, output exactly 'NO_POINTS'."
)


def chunk_text(
    text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP
) -> list[str]:
    """Split text into chunks with overlap to preserve context."""
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i : i + chunk_size])
        chunks.append(chunk)
        i += chunk_size - overlap
    return chunks


def extract_dhamma_points(text: str) -> str:
    return generate_content(
        contents=text,
        system_instruction=SYSTEM_INSTRUCTION,
    )


def main():
    input_dir = Path("output/corrected_pali")
    output_dir = Path("output/extracted")
    output_dir.mkdir(exist_ok=True)

    if not get_working_key():
        print("All API keys failed. Exiting.")
        return

    # Parse args: optional file (--test flag handled by provider)
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    specific_file = args[0] if args else None

    if specific_file:
        # If it's a full path, use it directly; otherwise look in input_dir
        if Path(specific_file).is_absolute() or Path(specific_file).exists():
            md_files = [Path(specific_file)]
        else:
            md_files = [input_dir / specific_file]
        if not md_files[0].exists():
            print(f"File not found: {md_files[0]}")
            return
    else:
        md_files = list(input_dir.glob("*.md"))
        if not md_files:
            print("No files found in 'corrected_pali/'. Run correct_pali.py first.")
            return

    print(f"Found {len(md_files)} files", flush=True)

    for file_path in md_files:
        final_output_path = output_dir / file_path.name
        if final_output_path.exists():
            print(f"Skipping '{file_path.name}', already extracted.")
            continue

        print(f"Extracting points from '{file_path.name}'...")
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()

        chunks = chunk_text(text)
        all_points = []

        for i, chunk in enumerate(chunks):
            print(f"  Chunk {i + 1}/{len(chunks)}...", flush=True)
            try:
                result = extract_dhamma_points(chunk)
                if "NO_POINTS" not in result.strip():
                    all_points.append(result.strip())
            except Exception as e:
                print(f"    Failed on chunk {i + 1}: {e}")

        if all_points:
            with open(final_output_path, "w", encoding="utf-8") as f:
                f.write("\n\n".join(all_points))
            print(f"Extraction saved to '{final_output_path.name}'.\n")
        else:
            print(f"No Dhamma points found in '{file_path.name}'.\n")

        print("  Waiting 5s between files...", flush=True)
        time.sleep(5)


if __name__ == "__main__":
    main()
