#!/usr/bin/env python3
"""Consolidates polished and extracted Dhamma sections into one tag-grouped database."""

import argparse
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from tools import printer as _p

pr = _p.printer

TAG_HEADER_RE = re.compile(r"^##\s+((?:\[[^\]]+\]\s*)+)$", re.MULTILINE)


@dataclass(frozen=True)
class SourceDocument:
    path: Path
    rel_path: Path
    is_polished: bool


@dataclass(frozen=True)
class TaggedSection:
    tag: str
    source: Path
    content: str


@dataclass(frozen=True)
class UntaggedSection:
    source: Path
    content: str


@dataclass(frozen=True)
class ConsolidationResult:
    source_count: int
    tagged_count: int
    untagged_count: int
    output_path: Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Consolidate extracted Dhamma sections into a master database."
    )
    parser.add_argument(
        "--polished-dir",
        type=Path,
        default=Path("output/polished"),
        help="Polished output directory to prefer",
    )
    parser.add_argument(
        "--extracted-dir",
        type=Path,
        default=Path("output/extracted"),
        help="Extracted output directory used as fallback",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("master_dhamma_database.md"),
        help="Master database path to write",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    result = consolidate(
        polished_dir=args.polished_dir,
        extracted_dir=args.extracted_dir,
        output_path=args.output,
    )
    pr.summary("sources", result.source_count)
    pr.summary("tagged sections", result.tagged_count)
    pr.summary("untagged sections", result.untagged_count)
    pr.green(f"Master database: {result.output_path}")
    return 0


def consolidate(
    polished_dir: Path = Path("output/polished"),
    extracted_dir: Path = Path("output/extracted"),
    output_path: Path = Path("master_dhamma_database.md"),
) -> ConsolidationResult:
    sources = build_source_map(polished_dir=polished_dir, extracted_dir=extracted_dir)
    tagged_by_tag: dict[str, list[TaggedSection]] = {}
    untagged: list[UntaggedSection] = []

    for source in sources:
        text = source.path.read_text(encoding="utf-8")
        tagged_sections, untagged_sections = parse_sections(text, source.rel_path)
        for section in tagged_sections:
            tagged_by_tag.setdefault(section.tag, []).append(section)
        untagged.extend(untagged_sections)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        render_database(tagged_by_tag, untagged),
        encoding="utf-8",
    )
    return ConsolidationResult(
        source_count=len(sources),
        tagged_count=sum(len(sections) for sections in tagged_by_tag.values()),
        untagged_count=len(untagged),
        output_path=output_path,
    )


def build_source_map(polished_dir: Path, extracted_dir: Path) -> list[SourceDocument]:
    source_by_key: dict[str, SourceDocument] = {}

    if polished_dir.exists():
        for path in sorted(
            polished_dir.rglob("*.md"), key=lambda item: str(item).lower()
        ):
            rel_path = path.relative_to(polished_dir)
            source_by_key[_rel_key(rel_path)] = SourceDocument(
                path=path,
                rel_path=rel_path,
                is_polished=True,
            )

    if extracted_dir.exists():
        for path in sorted(
            extracted_dir.rglob("*.md"), key=lambda item: str(item).lower()
        ):
            rel_path = path.relative_to(extracted_dir)
            source_by_key.setdefault(
                _rel_key(rel_path),
                SourceDocument(path=path, rel_path=rel_path, is_polished=False),
            )

    return sorted(
        source_by_key.values(), key=lambda source: str(source.rel_path).lower()
    )


def parse_sections(
    text: str,
    source: Path,
) -> tuple[list[TaggedSection], list[UntaggedSection]]:
    normalized_text = unicodedata.normalize("NFC", text)
    matches = list(TAG_HEADER_RE.finditer(normalized_text))
    if not matches:
        stripped = normalized_text.strip()
        return [], [
            UntaggedSection(source=source, content=stripped)
        ] if stripped else []

    tagged: list[TaggedSection] = []
    untagged: list[UntaggedSection] = []
    preamble = normalized_text[: matches[0].start()].strip()
    if preamble:
        untagged.append(UntaggedSection(source=source, content=preamble))

    for index, match in enumerate(matches):
        tag = unicodedata.normalize("NFC", match.group(1).strip())
        start = match.end()
        end = (
            matches[index + 1].start()
            if index + 1 < len(matches)
            else len(normalized_text)
        )
        content = normalized_text[start:end].strip()
        if content:
            tagged.append(TaggedSection(tag=tag, source=source, content=content))

    return tagged, untagged


def render_database(
    tagged_by_tag: dict[str, list[TaggedSection]],
    untagged: list[UntaggedSection],
) -> str:
    lines = ["# Master Dhamma Points Database", ""]

    for tag in sorted(tagged_by_tag, key=str.casefold):
        lines.extend([f"## {tag}", ""])
        for section in tagged_by_tag[tag]:
            lines.extend(
                [
                    f"### Source: {section.source.as_posix()}",
                    "",
                    section.content,
                    "",
                    "---",
                    "",
                ]
            )

    if untagged:
        lines.extend(["## Untagged Sources", ""])
        for section in untagged:
            lines.extend(
                [
                    f"### Source: {section.source.as_posix()}",
                    "",
                    section.content,
                    "",
                    "---",
                    "",
                ]
            )

    return "\n".join(lines).rstrip() + "\n"


def _rel_key(rel_path: Path) -> str:
    return unicodedata.normalize("NFC", rel_path.as_posix())


if __name__ == "__main__":
    raise SystemExit(main())
