"""Rename Latin-named thumbnails in output/thumbnails/russian to Russian descriptions."""

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from PIL import Image

# Ensure tools can be imported
sys.path.append(str(Path(__file__).parent.parent))

from tools.gemini import key_manager
from tools.printer import printer as pr
from google.genai import types

MODELS_TO_TRY = [
    "gemini-3.1-flash-lite-preview",
    "gemini-2.0-flash",
    "gemini-2.5-flash",
]


def normalize(s: str) -> str:
    """Normalize string to NFC representation."""
    return unicodedata.normalize("NFC", s)


def clean_name(name: str) -> str:
    """Extract and clean the core base name from a thumbnail filename."""
    # Remove date prefix YYYY-MM-DD -
    name = re.sub(r"^\d{4}-\d{2}-\d{2}\s*-\s*", "", name)
    # Remove monk suffix
    name = re.sub(r"\s*-\s*Bhikkhu\s+Devamitta$", "", name, flags=re.IGNORECASE)
    # Remove extension
    name = Path(name).stem
    return normalize(name).strip().lower()


def translate_subjects_batch(subjects: list[str]) -> dict[str, str]:
    """Translate a list of English descriptions into Russian in a single batch request."""
    if not subjects:
        return {}

    prompt = (
        "Translate the following list of English image subject descriptions into short, natural, lowercase Russian phrases "
        "(similar to 'весы на столе', 'поток воды', 'якорь на берегу').\n"
        "Return the result as a JSON object where the keys are the exact original English descriptions, and the values are their Russian translations.\n"
        "Return ONLY a valid JSON object, no markdown formatting (like ```json), no extra text.\n\n"
        f"{json.dumps(subjects, ensure_ascii=False, indent=2)}"
    )

    for model in MODELS_TO_TRY:
        try:
            response = key_manager.client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.0,
                    max_output_tokens=4096,
                ),
            )
            if response.text:
                text = response.text.strip()
                if text.startswith("```"):
                    text = re.sub(r"^```(?:json)?\s*", "", text)
                    text = re.sub(r"\s*```$", "", text)

                translations: dict[str, str] = json.loads(text.strip())
                cleaned = {}
                for k, v in translations.items():
                    val = v.strip().lower()
                    val = re.sub(r"[.\'\"`]+$", "", val)
                    val = re.sub(r"^[.\'\"`]+", "", val)
                    cleaned[k] = val.strip().lower()
                return cleaned
        except Exception as e:
            pr.amber(f"Warning: batch translation model {model} failed: {e}")

    raise RuntimeError("All models failed batch translation")


def translate_subject(english_text: str) -> str:
    """Translate a single English description to Russian (fallback)."""
    prompt = (
        "Translate the following English description of a visual image into a short, natural, lowercase Russian phrase "
        "describing the image's subject (similar to 'весы на столе', 'поток воды', 'якорь на берегу'). "
        "Return ONLY the translated Russian phrase, no punctuation, lowercase, no extra text:\n\n"
        f"{english_text}"
    )
    for model in MODELS_TO_TRY:
        try:
            response = key_manager.client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.0,
                    max_output_tokens=50,
                ),
            )
            if response.text:
                result = response.text.strip().lower()
                result = re.sub(r"[.\'\"`]+$", "", result)
                result = re.sub(r"^[.\'\"`]+", "", result)
                return result.strip().lower()
        except Exception as e:
            pr.amber(f"Warning: model {model} failed translating '{english_text}': {e}")
    raise RuntimeError(f"All models failed translating '{english_text}'")


def describe_image_multimodal(image_path: Path) -> str:
    """Use Gemini multimodal vision capability to describe the image in Russian."""
    prompt = (
        "Опиши, что изображено на картинке, короткой и естественной фразой на русском языке в нижнем регистре "
        "(например: 'весы на столе', 'поток воды', 'якорь на берегу'). "
        "Верни ТОЛЬКО эту фразу, без знаков препинания и без лишнего текста."
    )

    try:
        img = Image.open(image_path)
    except Exception as e:
        raise RuntimeError(f"Failed to open image {image_path}: {e}")

    for model in MODELS_TO_TRY:
        try:
            response = key_manager.client.models.generate_content(
                model=model,
                contents=[img, prompt],
                config=types.GenerateContentConfig(
                    temperature=0.0,
                    max_output_tokens=50,
                ),
            )
            if response.text:
                result = response.text.strip().lower()
                result = re.sub(r"[.\'\"`]+$", "", result)
                result = re.sub(r"^[.\'\"`]+", "", result)
                return result.strip().lower()
        except Exception as e:
            pr.amber(
                f"Warning: model {model} failed describing image {image_path.name}: {e}"
            )

    raise RuntimeError(f"All models failed describing image {image_path.name}")


def main() -> None:
    """Rename Latin-named thumbnails to Russian descriptions."""
    parser = argparse.ArgumentParser(
        description="Rename Latin-named Russian thumbnails based on subjects JSON or image contents."
    )
    parser.add_argument(
        "--commit", action="store_true", help="Perform the actual renaming of files."
    )
    args = parser.parse_args()

    json_path = Path("output/thumbnail_subjects.json")
    if not json_path.exists():
        pr.red(f"Error: Subjects file not found at {json_path}")
        sys.exit(1)

    subjects_data = json.loads(json_path.read_text(encoding="utf-8"))

    # Map cleaned JSON filenames to subjects
    json_map: dict[str, str] = {}
    for entry in subjects_data["subjects"]:
        cleaned = clean_name(entry["file"])
        json_map[cleaned] = entry["subject"]

    thumbnails_dir = Path("output/thumbnails/russian")
    if not thumbnails_dir.exists():
        pr.red(f"Error: Thumbnails directory not found at {thumbnails_dir}")
        sys.exit(1)

    latin_files: list[Path] = []
    cyrillic_pattern = re.compile(r"[а-яА-ЯёЁ]")

    for f in sorted(thumbnails_dir.iterdir()):
        if f.is_file() and not f.name.startswith("."):
            if not cyrillic_pattern.search(f.name):
                latin_files.append(f)

    if not latin_files:
        pr.green(
            "No files with only Latin characters found in the Russian thumbnails folder."
        )
        return

    pr.cyan(f"Found {len(latin_files)} files with only Latin characters to process.")

    # 1. Match files to English subjects
    matched_subjects: dict[Path, str] = {}
    unmatched_files: list[Path] = []

    for f in latin_files:
        cleaned_f = clean_name(f.name)
        subject = json_map.get(cleaned_f)

        if not subject:
            # Try substring match
            for k, v in json_map.items():
                if cleaned_f in k or k in cleaned_f:
                    subject = v
                    break

        if subject:
            matched_subjects[f] = subject
        else:
            unmatched_files.append(f)

    # 2. Batch translate all matched subjects
    translated_map: dict[str, str] = {}
    if matched_subjects:
        unique_subjects = list(set(matched_subjects.values()))
        pr.green_tmr(f"Translating {len(unique_subjects)} unique subjects in batch")
        try:
            translated_map = translate_subjects_batch(unique_subjects)
            pr.yes("Done")
        except Exception as e:
            pr.no(f"Batch translation failed: {e}")
            sys.exit(1)

    # 3. Construct renames
    renames: list[tuple[Path, Path]] = []
    for f in latin_files:
        if f in matched_subjects:
            subj = matched_subjects[f]
            desc = translated_map.get(subj)
            if not desc:
                pr.amber(
                    f"Warning: Could not find translation for '{subj}', falling back to single request."
                )
                try:
                    desc = translate_subject(subj)
                except Exception as e:
                    pr.red(f"Failed fallback translation for '{subj}': {e}")
                    continue
        else:
            pr.cyan_tmr(f"Querying multimodal description for unmatched file {f.name}")
            try:
                desc = describe_image_multimodal(f)
                pr.yes(f"Described -> '{desc}'")
            except Exception as e:
                pr.no(f"Failed: {e}")
                continue

        # Form the new filename
        new_name = f"{desc}.jpg"
        new_path = thumbnails_dir / new_name
        renames.append((f, new_path))

    # Print proposed renames summary
    pr.cyan("\n--- Proposed Renaming Plan ---")
    for old_path, new_path in renames:
        pr.white(f"  {old_path.name}  ==>  {new_path.name}")

    if not args.commit:
        pr.amber("\n[DRY RUN] Run again with --commit to apply the changes.")
    else:
        pr.green_title("\nApplying renames...")
        success_count = 0
        for old_path, new_path in renames:
            try:
                pr.green_tmr(f"Renaming {old_path.name}")
                # Ensure unique filename if target exists
                final_new_path = new_path
                counter = 1
                while final_new_path.exists() and final_new_path != old_path:
                    final_new_path = new_path.with_name(
                        f"{new_path.stem}_{counter}.jpg"
                    )
                    counter += 1

                old_path.rename(final_new_path)
                pr.yes(f"-> {final_new_path.name}")
                success_count += 1
            except Exception as e:
                pr.no(f"Failed: {e}")

        pr.green(f"\nSuccessfully renamed {success_count}/{len(renames)} files.")


if __name__ == "__main__":
    main()
