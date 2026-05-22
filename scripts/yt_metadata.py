"""Generates YouTube metadata (title and description) for Dhamma talks using Gemini API."""

import argparse
import concurrent.futures
import re
import time
import unicodedata
from pathlib import Path

from tools.dry_run import is_pipeline_dry_run
from tools.glossary import TAG_POOL_EN, TAG_POOL_RU, TAG_SYNC_GROUPS
from tools.printer import printer as pr
from tools.provider import (
    build_cacheable_contents,
    generate_with_timeout,
    get_working_key,
)
from tools.uploader_common import BIO_LINKS


DEFAULT_SPEAKER: dict[str, str] = {
    "en": "Bhikkhu Devamitta",
    "ru": "Бхиккху Дэвамитта",
}


def _name_in_stem(stem: str, name: str) -> bool:
    """True if any word from name appears anywhere in stem (case-insensitive)."""
    stem_lower = stem.lower()
    return any(word.lower() in stem_lower for word in name.split())


def _date_from_stem(stem: str) -> str:
    """Extract DD-MM-YYYY from a stem starting with YYYY-MM-DD or DD-MM-YYYY."""
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", stem)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    m = re.match(r"^(\d{2})-(\d{2})-(\d{4})", stem)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return ""


TAG_POOLS: dict[str, list[str]] = {
    "ru": TAG_POOL_RU,
    "en": TAG_POOL_EN,
}

LANG_TO_FOLDER: dict[str, str] = {"ru": "russian", "en": "english"}


def enrich_tags(tags: str, lang: str) -> str:
    """Add Pāli counterparts and synonym pairs missing from LLM tag output."""
    tag_list = tags.split()
    tag_set = {t.lstrip("#") for t in tag_list}
    for group in TAG_SYNC_GROUPS:
        group_tags: list[str] = group[lang]
        if any(t in tag_set for t in group_tags):
            for t in group_tags:
                if t not in tag_set:
                    tag_list.append(f"#{t}")
                    tag_set.add(t)
    return " ".join(tag_list)


def get_system_instruction(lang: str) -> str:
    pool_str = " ".join(TAG_POOLS[lang])
    if lang == "ru":
        return f"""You are preparing video upload metadata for a recorded Dhamma (Buddhist teaching) talk by a senior meditation teacher. The talk is in Russian.

CONTEXT:
- These are intimate Theravāda teaching sessions in Russian, not academic lectures.
- The audience is Russian-speaking practitioners and people sincerely interested in Buddhist meditation and the Dhamma.
- Sessions often involve Q&A exchanges between the teacher and student(s).
- Pāli terms may appear in transliteration (e.g., Ниббана, Сатипаттхана, Сангха). Keep them as-is if they appear in the transcript.

TITLE REQUIREMENTS:
Determine from the transcript whether this talk is PART OF A SERIES (a cycle of talks on one topic) or a STANDALONE talk.

FORMAT FOR A SERIES TALK:
  СЕРИЯ В ВЕРХНЕМ РЕГИСТРЕ | Конкретная подтема с Ключевыми Словами | Часть N
  - Series name: ALL CAPS (e.g. СОЗЕРЦАНИЕ ДХАММ, ЧЕТЫРЕ ОСНОВЫ ВНИМАТЕЛЬНОСТИ).
  - Specific subtopic: title case with key Dhamma terms capitalized.
  - Include "Часть N" only if the part number is clearly stated in the transcript; omit it if uncertain.
  Example: СОЗЕРЦАНИЕ ДХАММ | Шесть областей ВОСПРИЯТИЯ | Часть 14

FORMAT FOR A STANDALONE TALK:
  Тема с Капитализированными Ключевыми Словами
  - Title case; capitalize key Dhamma and meditation terms (Мудрость, Осознанность, Медитация, Ниббана, Дхамма, Самадхи, Карма).
  - 3–5 words.
  Example: Развитие Мудрости через Осознанность

Additional rules for both formats:
- Do NOT use generic openers: "Беседа о...", "Лекция:", "Обсуждение...".
- Avoid vague spiritual marketing language: "Глубокий", "Удивительный", "Невероятный".
- Do NOT include the speaker name — it will be added automatically.
- Output in Russian.

DESCRIPTION REQUIREMENTS:
- Tone: modest, clear, grounded — for a sincere practitioner, not a casual browser.
- Use humble, impersonal sentence openers. GOOD examples: "Объясняется...", "В этой беседе разбирается...", "Рассматривается...", "Раскрывается...".
- AVOID self-important or formal openers such as: "В этом учении объясняется...", "Данное учение посвящено...", "Это учение раскрывает...".
- Write exactly 2–3 sentences (overview, what the listener gains, one notable analogy or insight).
- If the talk covers multiple distinct topics or chapters: after the 2–3 sentences, add a bullet list of 3–8 main topics covered (each bullet ≤ 10 words, no hashtags).
- Do NOT use marketing language.
- NEVER mention "личная история". Focus on the Dhamma point being illustrated.
- NEVER reference the speaker directly. Keep descriptions impersonal and focused on the Dhamma.
- Do NOT include any hashtags in the description text. Tags go on the TAGS line only.
- Output in Russian.

TAGS REQUIREMENTS:
- Pool of approved tags: {pool_str}
- Select 8–12 tags from the pool that best match THIS specific talk's content.
- You may add up to 3 extra tags NOT in the pool ONLY if they name a very specific, unambiguous topic clearly present in this talk (e.g. a specific Pāli concept, a distinct practice method).
- Output all tags on one line, space-separated, each starting with #.

OUTPUT FORMAT:
Respond with EXACTLY three lines. No extra text, no markdown, no explanations.

TITLE: [suggested title in Russian]
DESCRIPTION: [suggested description in Russian]
TAGS: [8–12 hashtags from the pool, space-separated]
"""
    else:
        return f"""You are preparing video upload metadata for a recorded Dhamma (Buddhist teaching) talk by a senior meditation teacher. The talk is in English.

CONTEXT:
- These are intimate Theravāda teaching sessions in English, not academic lectures.
- The teacher is a Theravāda monk.
- The audience is English-speaking practitioners and people sincerely interested in Buddhist meditation and the Dhamma.
- Sessions often involve Q&A exchanges between the teacher and student(s).
- Pāli terms are used frequently (e.g., Nibbāna, Satipaṭṭhāna, Saṅgha). Use correct Pāli diacritics where possible.

TITLE REQUIREMENTS:
Determine from the transcript whether this talk is PART OF A SERIES (a cycle of talks on one topic) or a STANDALONE talk.

FORMAT FOR A SERIES TALK:
  SERIES NAME IN ALL CAPS | Specific Subtopic with Key Terms | Part N
  - Series name: ALL CAPS (e.g. CONTEMPLATION OF DHAMMAS, FOUR FOUNDATIONS OF MINDFULNESS).
  - Specific subtopic: title case with key Dhamma terms capitalized.
  - Include "Part N" only if the part number is clearly stated in the transcript; omit it if uncertain.
  Example: CONTEMPLATION OF DHAMMAS | Six Spheres of PERCEPTION | Part 14

FORMAT FOR A STANDALONE TALK:
  Topic with Capitalized Key Dhamma Terms
  - Title case; capitalize key Dhamma and meditation terms (Wisdom, Mindfulness, Meditation, Nibbāna, Dhamma, Samādhi, Kamma).
  - 3–5 words.
  Example: Developing Wisdom through Mindfulness

Additional rules for both formats:
- Do NOT use generic openers: "Talk about...", "Lecture on:", "Discussion regarding...".
- Avoid vague spiritual marketing language: "Deep", "Amazing", "Incredible".
- Do NOT include the speaker name — it will be added automatically.
- Output in English.

DESCRIPTION REQUIREMENTS:
- Tone: modest, clear, grounded — for a sincere practitioner, not a casual browser.
- Use humble, impersonal sentence openers. GOOD examples: "The talk explains...", "This session explores...", "An examination of...", "A reflection on...".
- AVOID self-important or formal openers such as: "This teaching explains...", "This lecture is dedicated to...", "This talk reveals...".
- Write exactly 2–3 sentences (overview, what the listener gains, one notable analogy or insight).
- If the talk covers multiple distinct topics or chapters: after the 2–3 sentences, add a bullet list of 3–8 main topics covered (each bullet ≤ 10 words, no hashtags).
- Do NOT include any hashtags in the description text. Tags go on the TAGS line only.
- Output in English.

TAGS REQUIREMENTS:
- Pool of approved tags: {pool_str}
- Select 8–12 tags from the pool that best match THIS specific talk's content.
- You may add up to 3 extra tags NOT in the pool ONLY if they name a very specific, unambiguous topic clearly present in this talk (e.g. a specific Pāli concept, a distinct practice method).
- Output all tags on one line, space-separated, each starting with #.

OUTPUT FORMAT:
Respond with EXACTLY three lines. No extra text, no markdown, no explanations.

TITLE: [suggested title in English]
DESCRIPTION: [suggested description in English]
TAGS: [8–12 hashtags from the pool, space-separated]
"""


def generate_metadata(text: str, lang: str) -> str:
    """Calls Gemini API to generate metadata for a given talk transcript."""
    return generate_with_timeout(
        contents=build_cacheable_contents(text),
        system_instruction=get_system_instruction(lang),
    )


def _write_dry_run_entry(
    output_file: Path,
    file_path: Path,
    lang: str,
    media: str,
    speaker_name: str | None,
    bio_link: str | None = None,
) -> None:
    """Writes a clearly-marked stub entry to the review file for pipeline dry-run."""
    nfc_name = unicodedata.normalize("NFC", file_path.name)
    speaker_suffix = ""
    if speaker_name and not _name_in_stem(file_path.stem, speaker_name):
        speaker_suffix = f" | {speaker_name}"
    title = f"[DRY_RUN] {file_path.stem}{speaker_suffix}"
    dry_run_desc = "[DRY_RUN] Dry run pipeline trace."
    if bio_link:
        dry_run_desc = f"{dry_run_desc}\n\n{bio_link}"
    section = (
        f"\n--- \n"
        f"## Source: {nfc_name}\n"
        f"**Recording Date:** {_date_from_stem(file_path.stem) or '01-01-2000'}\n"
        f"**Approved:** yes\n"
        f"**Media:** {media}\n"
        f"**Suggested Title:** {title}\n"
        f"**Suggested Description:** {dry_run_desc}\n\n"
        f"**Suggested Tags:** #dhamma\n"
    )
    output_file.parent.mkdir(parents=True, exist_ok=True)
    if not output_file.exists():
        header_lang = "Russian" if lang == "ru" else "English"
        output_file.write_text(
            f"# {header_lang} Audio Metadata Review (dry-run)\n"
            "Dry run stub — will be removed after pipeline completes.\n",
            encoding="utf-8",
        )
    with output_file.open("a", encoding="utf-8") as fh:
        fh.write(section)


def process_files(
    md_files: list[Path],
    lang: str,
    output_file_path: str,
    folder_name: str,
    speaker_name: str | None = None,
    media: str = "audio",
    dry_run: bool = False,
    bio_link: str | None = None,
) -> None:
    """Processes a list of markdown files and appends results to the review file."""
    output_file = Path(output_file_path)

    # Resume logic: skip files already written to the output file
    already_done: set[str] = set()
    if output_file.exists():
        existing = output_file.read_text(encoding="utf-8")
        already_done = {
            unicodedata.normalize("NFC", s)
            for s in re.findall(r"## Source: (.+)", existing)
        }

    pending = [
        f for f in md_files if unicodedata.normalize("NFC", f.name) not in already_done
    ]

    if not pending:
        pr.green(f"[{folder_name}] All files already processed.")
        return

    if dry_run:
        pr.green(f"[DRY RUN] Input:  {pending[0].parent if pending else 'N/A'}")
        pr.green(f"[DRY RUN] Output: {output_file}")
        for f in pending:
            pr.white(f"  {f} → {output_file}")
        if is_pipeline_dry_run():
            for f in pending:
                _write_dry_run_entry(
                    output_file, f, lang, media, speaker_name, bio_link
                )
        return

    # Write header only for a fresh file
    output_file.parent.mkdir(parents=True, exist_ok=True)
    if not output_file.exists():
        header_lang = "Russian" if lang == "ru" else "English"
        output_file.write_text(
            f"# {header_lang} Audio Metadata Review ({folder_name})\n"
            "Fill Recording Date (DD-MM-YYYY), review title/description/tags, then set Approved: yes.\n",
            encoding="utf-8",
        )

    pr.green(f"[{folder_name}] Processing {len(pending)} files → '{output_file}'.")
    total = len(pending)

    speaker_suffix = f" | {speaker_name}" if speaker_name else ""

    for i, file_path in enumerate(pending, 1):
        pr.green(f"  {i}/{total} '{file_path.name}'...")
        try:
            text = file_path.read_text(encoding="utf-8")
            try:
                metadata = generate_metadata(text, lang)
            except concurrent.futures.TimeoutError:
                pr.amber(f"    Timeout on '{file_path.name}' — skipping.")
                continue

            title = ""
            description = ""
            tags = ""
            for line in metadata.strip().split("\n"):
                if line.upper().startswith("TITLE:"):
                    title = line[len("TITLE:") :].strip() + speaker_suffix
                elif line.upper().startswith("DESCRIPTION:"):
                    description = line[len("DESCRIPTION:") :].strip()
                elif line.upper().startswith("TAGS:"):
                    tags = line[len("TAGS:") :].strip()

            tags = enrich_tags(tags, lang)
            if bio_link:
                description = f"{description}\n\n{bio_link}"

            section = (
                f"\n--- \n"
                f"## Source: {unicodedata.normalize('NFC', file_path.name)}\n"
                f"**Recording Date:** {_date_from_stem(file_path.stem)}\n"
                f"**Approved:** no\n"
                f"**Media:** {media}\n"
                f"**Suggested Title:** {title}\n"
                f"**Suggested Description:** {description}\n\n"
                f"**Suggested Tags:** {tags}\n"
            )
            with output_file.open("a", encoding="utf-8") as fh:
                fh.write(section)

        except Exception as e:
            pr.no(f"    Failed on '{file_path.name}': {e}")

        if total > 1 and i < total:
            pr.white("    Waiting 5s...")
            time.sleep(5)

    pr.green(f"[{folder_name}] Done. Review file: '{output_file}'.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate YouTube metadata suggestions for Dhamma talks."
    )
    parser.add_argument(
        "--lang",
        type=str,
        default=None,
        choices=["ru", "en"],
        help="Language of the talk (ru|en). Omit to skip bio link and use English defaults.",
    )
    parser.add_argument(
        "--folder",
        type=str,
        help="Subfolder in output/transcribed/ to process. Defaults to lang-based folder (ru→russian, en→english).",
    )
    parser.add_argument(
        "--output-file",
        type=str,
        default="",
        help="Override output file path.",
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
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Process only the first N transcript files (0=unlimited).",
    )
    parser.add_argument(
        "--name",
        type=str,
        help="Speaker name override for titles",
    )
    parser.add_argument(
        "--video-mode",
        action="store_true",
        help="Mark new entries as Media: video instead of audio.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be processed; create stub review entries for pipeline propagation.",
    )
    args = parser.parse_args()
    media = "video" if args.video_mode else "audio"

    # lang may be None when called without --lang; fall back to "en" for processing
    processing_lang: str = args.lang or "en"
    bio_link: str | None = (
        BIO_LINKS.get(args.lang)
        if args.lang is not None and args.name is None
        else None
    )

    # Effective speaker: --name > lang default > None (no lang + no name = empty)
    if args.name:
        effective_speaker: str | None = args.name
    elif args.lang:
        effective_speaker = DEFAULT_SPEAKER[args.lang]
    else:
        effective_speaker = None

    transcribed_base = Path("output/transcribed")
    if not transcribed_base.exists():
        pr.no(f"Base directory not found: {transcribed_base}")
        return

    if not args.dry_run and not get_working_key():
        pr.no("All API keys failed. Exiting.")
        return

    # Handle single file mode
    if args.file:
        file_path = Path(args.file)
        if not file_path.exists() and args.folder:
            file_path = transcribed_base / args.folder / args.file
        if not file_path.exists():
            pr.no(f"File not found: {args.file}")
            return

        folder_name = args.folder or file_path.parent.name
        lang_folder = LANG_TO_FOLDER.get(processing_lang, "english")
        out_file_path = args.output_file or f"reviews/{lang_folder}_review.md"
        process_files(
            [file_path],
            processing_lang,
            out_file_path,
            folder_name,
            speaker_name=effective_speaker,
            media=media,
            dry_run=args.dry_run,
            bio_link=bio_link,
        )
        return

    # Determine folders to process
    if args.folder is not None:
        folders = [transcribed_base / args.folder]
    else:
        folders = [transcribed_base / LANG_TO_FOLDER.get(processing_lang, "english")]

    if not folders:
        pr.no("No subfolders found to process.")
        return

    # Phase 1: Collect all pending files across all folders
    all_pending_groups: list[tuple[list[Path], str, str]] = []
    lang_folder = LANG_TO_FOLDER.get(processing_lang, "english")
    for folder_path in folders:
        folder_name = folder_path.name
        md_files = sorted(list(folder_path.glob("*.md")))
        if not md_files:
            continue

        out_file_path = args.output_file or f"reviews/{lang_folder}_review.md"

        output_file = Path(out_file_path)
        already_done: set[str] = set()
        if output_file.exists():
            existing = output_file.read_text(encoding="utf-8")
            already_done = {
                unicodedata.normalize("NFC", s)
                for s in re.findall(r"## Source: (.+)", existing)
            }

        pending = [
            f
            for f in md_files
            if unicodedata.normalize("NFC", f.name) not in already_done
        ]
        if pending:
            all_pending_groups.append((pending, folder_name, out_file_path))

    # Phase 2: Apply global limit
    if args.limit > 0:
        remaining = args.limit
        capped_groups: list[tuple[list[Path], str, str]] = []
        for pending, folder_name, out_file_path in all_pending_groups:
            if remaining <= 0:
                break
            capped = pending[:remaining]
            capped_groups.append((capped, folder_name, out_file_path))
            remaining -= len(capped)
        all_pending_groups = capped_groups

    if not all_pending_groups:
        pr.green("Nothing to do.")
        return

    # Phase 3: Process
    for pending, folder_name, out_file_path in all_pending_groups:
        process_files(
            pending,
            processing_lang,
            out_file_path,
            folder_name,
            speaker_name=effective_speaker,
            media=media,
            dry_run=args.dry_run,
            bio_link=bio_link,
        )


if __name__ == "__main__":
    main()
