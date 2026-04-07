from pathlib import Path
from google import genai
from google.genai import types
from tenacity import (
    retry,
    wait_exponential,
    stop_after_attempt,
    retry_if_exception_type,
)
from dotenv import load_dotenv

load_dotenv()
client = genai.Client()


def chunk_text_with_overlap(text: str, chunk_size=2500, overlap=300) -> list[str]:
    """Splits text with overlap to preserve dialog context for extraction."""
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i : i + chunk_size])
        chunks.append(chunk)
        i += chunk_size - overlap
    return chunks


@retry(
    wait=wait_exponential(multiplier=2, min=4, max=60),
    stop=stop_after_attempt(5),
    retry=retry_if_exception_type(Exception),
)
def extract_dhamma_points(chunk: str) -> str:
    system_instruction = (
        "You are an expert in early Buddhism. Analyze this transcript chunk, which is a dialog between a student and a teacher. "
        "1. Extract ONLY core Dhamma points. Exclude all logistics, casual talk, or pleasantries. "
        "2. Evaluate claims before extracting. If the student makes an incorrect statement that the teacher subsequently corrects, extract the teacher's clarification, NOT the student's premise. "
        "3. Output as a clean Markdown bulleted list. If no Dhamma points exist in this chunk, output exactly 'NO_POINTS'."
    )

    response = client.models.generate_content(
        model="gemini-1.5-flash",
        contents=chunk,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.1,
        ),
    )
    if response.text is None:
        raise ValueError("Empty response from Gemini API")
    return response.text


def main():
    input_dir = Path("corrected")
    output_dir = Path("extracted")
    output_dir.mkdir(exist_ok=True)

    md_files = list(input_dir.glob("*.md"))
    if not md_files:
        print("No files found in 'corrected/'. Run correct_pali.py first.")
        return

    for file_path in md_files:
        final_output_path = output_dir / file_path.name
        if final_output_path.exists():
            print(f"Skipping '{file_path.name}', already extracted.")
            continue

        print(f"Extracting points from '{file_path.name}'...")
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()

        chunks = chunk_text_with_overlap(text)
        extracted_points = []

        for i, chunk in enumerate(chunks):
            print(f"  Chunk {i + 1}/{len(chunks)}...")
            try:
                result = extract_dhamma_points(chunk)
                if "NO_POINTS" not in result.strip():
                    extracted_points.append(result)
            except Exception as e:
                print(f"  Failed on chunk {i + 1}: {e}")

        if extracted_points:
            with open(final_output_path, "w", encoding="utf-8") as f:
                f.write("\n\n".join(extracted_points))
            print(f"Extraction saved to '{final_output_path.name}'.\n")


if __name__ == "__main__":
    main()
