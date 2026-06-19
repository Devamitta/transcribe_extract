"""Scans polished or extracted Dhamma output for deterministic privacy leaks."""

import argparse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import unicodedata

from tools import printer as _p
from tools.privacy import Fix, Hit, apply_fixes, scan_text

pr = _p.printer


@dataclass(frozen=True)
class SourceFile:
    path: Path
    rel_path: Path
    is_polished: bool


@dataclass(frozen=True)
class FilePrivacyResult:
    source: SourceFile
    hits: list[Hit]
    fixes: list[Fix]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scan Dhamma output for privacy leaks."
    )
    parser.add_argument(
        "--polished-dir",
        type=Path,
        default=Path("output/polished"),
        help="Polished output directory to scan first",
    )
    parser.add_argument(
        "--extracted-dir",
        type=Path,
        default=Path("output/extracted"),
        help="Extracted output directory used as fallback",
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=Path("reports/privacy"),
        help="Directory for privacy scan reports",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Rewrite flagged polished files with generic replacements",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    sources = build_source_map(args.polished_dir, args.extracted_dir)
    results = scan_sources(sources, fix=args.fix)
    report_path = write_report(results, args.report_dir, fix=args.fix)

    hit_count = sum(len(result.hits) for result in results)
    fix_count = sum(sum(fix.count for fix in result.fixes) for result in results)
    pr.summary("privacy files", len(results))
    pr.summary("privacy hits", hit_count)
    pr.summary("privacy fixes", fix_count)
    pr.green(f"Privacy report: {report_path}")
    return 0


def build_source_map(polished_dir: Path, extracted_dir: Path) -> list[SourceFile]:
    source_by_key: dict[str, SourceFile] = {}

    if polished_dir.exists():
        for path in sorted(
            polished_dir.rglob("*.md"), key=lambda item: str(item).lower()
        ):
            rel_path = path.relative_to(polished_dir)
            source_by_key[_rel_key(rel_path)] = SourceFile(
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
                SourceFile(path=path, rel_path=rel_path, is_polished=False),
            )

    return sorted(source_by_key.values(), key=lambda item: str(item.rel_path).lower())


def scan_sources(
    sources: list[SourceFile], fix: bool = False
) -> list[FilePrivacyResult]:
    results: list[FilePrivacyResult] = []
    for source in sources:
        text = source.path.read_text(encoding="utf-8")
        hits = scan_text(text)
        fixes: list[Fix] = []
        if fix and hits and source.is_polished:
            fixed_text, fixes = apply_fixes(text)
            source.path.write_text(fixed_text, encoding="utf-8")
        results.append(FilePrivacyResult(source=source, hits=hits, fixes=fixes))
    return results


def write_report(
    results: list[FilePrivacyResult],
    report_dir: Path,
    fix: bool = False,
) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"privacy_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    report_path.write_text(_render_report(results, fix=fix), encoding="utf-8")
    return report_path


def _render_report(results: list[FilePrivacyResult], fix: bool = False) -> str:
    lines = [
        "# Privacy Scan Report",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        f"Fix mode: {'yes' if fix else 'no'}",
        "",
    ]

    if not results:
        lines.append("_No files scanned._")
        return "\n".join(lines)

    for result in results:
        if not result.hits and not result.fixes:
            continue
        source_kind = "polished" if result.source.is_polished else "extracted"
        lines.extend(
            [
                f"## {result.source.rel_path.as_posix()}",
                "",
                f"Source: {source_kind}",
                "",
            ]
        )
        if result.hits:
            lines.append("### Hits")
            for hit in result.hits:
                lines.append(f"- `{hit.category}` `{hit.term}`")
                lines.append(f"  - Context: {hit.context}")
            lines.append("")
        if result.fixes:
            lines.append("### Fixes")
            for fix_item in result.fixes:
                lines.append(
                    f"- `{fix_item.term}` -> `{fix_item.replacement}` "
                    f"({fix_item.count})"
                )
            lines.append("")
        elif fix and not result.source.is_polished:
            lines.append("_Fix skipped: fallback extracted file was not rewritten._")
            lines.append("")

    if len(lines) == 5:
        lines.append("_No privacy hits found._")

    return "\n".join(lines)


def _rel_key(rel_path: Path) -> str:
    return unicodedata.normalize("NFC", rel_path.as_posix())


if __name__ == "__main__":
    raise SystemExit(main())
