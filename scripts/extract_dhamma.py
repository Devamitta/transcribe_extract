from pathlib import Path
import time

from tools.gemini import generate_content, get_working_key

CHUNK_SIZE = 5000
CHUNK_OVERLAP = 500

SYSTEM_INSTRUCTION = (
    "You are an expert in early Buddhism. Analyze this transcript segment, which is a dialog between a student and a teacher. "
    "CRITICAL INSTRUCTIONS - READ CAREFULLY:\n"
    "1. EXTRACT EVERYTHING: Extract ALL Dhamma points, teachings, explanations, reasoning, nuances, and examples from the teacher's responses. "
    "2. DO NOT SUMMARIZE: Keep the full explanations with details. Do not truncate or condense. "
    "3. EXTRACT DENSITY TARGET: Aim to extract ~10-15% of the input text as output. If input is 5000 words, output should be ~500-750 words. "
    "4. Include the reasoning behind teachings, not just conclusions. "
    "5. Include examples, analogies, and stories the teacher uses. "
    "6. Exclude ONLY: logistics, scheduling, casual pleasantries, or off-topic chatter. "
    "7. Evaluate claims: if student makes incorrect statement and teacher corrects it, extract the teacher's clarification with full explanation. "
    "8. Output as a clean Markdown bulleted list. Each bullet point MUST include a topic tag in brackets at the start, "
    "   e.g. '[kamma] The law of kamma explains that actions have consequences...' "
    "9. Use these tags when relevant: [kamma], [satipaṭṭhāna], [jhāna], [mettā], [dukkha], [nibbāna], [sīla], [samādhi], [paññā], [four-noble-truths], [noble-eightfold-path], [seven-factors], [brahmavihāra], [anattā], [khandha], [upekkhā], [asubha]. "
    "10. If a point doesn't fit any specific tag, use [general]. "
    "11. If no Dhamma points exist in this transcript, output exactly 'NO_POINTS'."
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
        max_output_tokens=32768,
        temperature=0.1,
    )


def main():
    input_dir = Path("output/corrected_pali")
    output_dir = Path("output/extracted")
    output_dir.mkdir(exist_ok=True)

    if not get_working_key():
        print("All API keys failed. Exiting.")
        return

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
