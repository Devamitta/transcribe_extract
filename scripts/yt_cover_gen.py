"""Composites text overlays onto existing thumbnail images to create YouTube cover thumbnails."""

import argparse
import dataclasses
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

from tools.dry_run import create_stub, is_pipeline_dry_run
from tools.printer import printer as pr
from tools.source_scope import read_source_filter, source_matches_filter
from tools.uploader_common import get_uploaded_history_entry, load_nested_history

LANG_TO_FOLDER: dict[str, str] = {"ru": "russian", "en": "english"}
HISTORY_PATH = Path("output/youtube_history.json")
_TITLE_SEGMENT_RE = re.compile(r"\s*(?:[|:;•·?!]+|[/\\]+|[–—]+)\s*|\s+-\s+|[,\.]\s+")


@dataclasses.dataclass
class OverlayCfg:
    gradient_height_pct: float
    gradient_max_alpha: int
    bottom_gradient_height_pct: float
    font_path: str
    ru_font_path: str
    title_size_pct: float
    title_stroke_pct: float
    teacher_size_pct: float
    text_x_pct: float
    max_text_w_pct: float
    shadow_offset: int


def load_overlay_cfg() -> OverlayCfg:
    return OverlayCfg(
        gradient_height_pct=float(os.environ.get("COVER_GRADIENT_HEIGHT_PCT", "0.45")),
        gradient_max_alpha=int(os.environ.get("COVER_GRADIENT_MAX_ALPHA", "200")),
        bottom_gradient_height_pct=float(
            os.environ.get("COVER_BOTTOM_GRADIENT_HEIGHT_PCT", "0.20")
        ),
        font_path=os.environ.get("COVER_FONT_PATH", ""),
        ru_font_path=os.environ.get("COVER_RU_FONT_PATH", ""),
        title_size_pct=float(os.environ.get("COVER_TITLE_SIZE_PCT", "0.33")),
        title_stroke_pct=float(os.environ.get("COVER_TITLE_STROKE_PCT", "0.10")),
        teacher_size_pct=float(os.environ.get("COVER_TEACHER_SIZE_PCT", "0.07")),
        text_x_pct=float(os.environ.get("COVER_TEXT_X_PCT", "0.04")),
        max_text_w_pct=float(os.environ.get("COVER_MAX_TEXT_W_PCT", "0.85")),
        shadow_offset=int(os.environ.get("COVER_SHADOW_OFFSET", "1")),
    )


def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "", name).strip(". ")


def extract_teacher(title: str) -> tuple[str, str]:
    """Split 'Talk Title | Teacher Name' into (title_part, teacher_part)."""
    parts = [p.strip() for p in title.split("|")]
    if len(parts) > 1:
        return " | ".join(parts[:-1]), parts[-1]
    return title, ""


def parse_review(review_path: Path) -> list[dict[str, str]]:
    """Parse the review markdown file for approved talks with recording dates."""
    content = review_path.read_text(encoding="utf-8")
    sections = content.split("\n---")
    talks = []

    for section in sections:
        section = section.strip()
        if not section or "Source:" not in section:
            continue

        talk = {}

        # Source line
        source_match = re.search(r"Source:\s*(.+)", section)
        if source_match:
            source_full = source_match.group(1).strip()
            talk["source"] = Path(source_full).stem

        # Title
        title_match = re.search(r"\*\*Suggested Title:\*\*\s*(.+)", section)
        if title_match:
            talk["title"] = title_match.group(1).strip()

        # Approved field
        approved_m = re.search(r"\*\*Approved:\*\*\s*(yes|no)", section, re.IGNORECASE)
        talk["approved"] = approved_m.group(1).lower() == "yes" if approved_m else False

        # Recording Date (DD-MM-YYYY)
        date_match = re.search(r"\*\*Recording Date:\*\*\s*([\d-]+)", section)
        if date_match:
            talk["recording_date"] = date_match.group(1).strip()

        # Description
        desc_match = re.search(
            r"\*\*Suggested Description:\*\*\s*(.*)", section, re.DOTALL
        )
        if desc_match:
            desc_text = desc_match.group(1).strip()
            desc_lines = []
            for line in desc_text.splitlines():
                if (
                    line.startswith("**")
                    or line.startswith("##")
                    or line.startswith("---")
                ):
                    break
                desc_lines.append(line)
            talk["description"] = "\n".join(desc_lines).strip()

        media_match = re.search(
            r"\*\*Media:\*\*\s*(video|audio)", section, re.IGNORECASE
        )
        talk["media"] = media_match.group(1).lower() if media_match else "audio"

        if "title" in talk and talk.get("recording_date") and talk.get("approved"):
            talks.append(talk)

    return talks


def _load_font(
    size: int, font_path: str = ""
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [font_path] if font_path else []
    candidates += [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Arial.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    max_width: int,
) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        test = " ".join(current + [word])
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current.append(word)
        else:
            if current:
                lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))
    return lines


def _split_title_segments(text: str) -> list[str]:
    """Split cover titles at common title separators that should force line breaks."""
    return [
        segment.strip() for segment in _TITLE_SEGMENT_RE.split(text) if segment.strip()
    ]


def add_text_overlay(img_path: Path, title: str, cfg: OverlayCfg) -> None:
    img = Image.open(img_path).convert("RGBA")
    w, h = img.size

    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw_overlay = ImageDraw.Draw(overlay)

    # Top gradient — darkens upper portion for title readability
    gradient_h = int(h * cfg.gradient_height_pct)
    for y in range(gradient_h):
        alpha = int(cfg.gradient_max_alpha * (1 - y / gradient_h))
        draw_overlay.line([(0, y), (w, y)], fill=(0, 0, 0, alpha))

    # Bottom gradient — darkens lower portion for teacher name readability
    bottom_h = int(h * cfg.bottom_gradient_height_pct)
    for y in range(bottom_h):
        alpha = int(cfg.gradient_max_alpha * y / bottom_h)
        draw_overlay.line(
            [(0, h - bottom_h + y), (w, h - bottom_h + y)], fill=(0, 0, 0, alpha)
        )

    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    title_part, teacher = extract_teacher(title)
    max_text_w = int(w * cfg.max_text_w_pct)
    margin = int(w * cfg.text_x_pct)

    # --- Title: top-left ---
    title_sz = max(40, int(h * cfg.title_size_pct))
    f_title = _load_font(title_sz, cfg.font_path)
    lines: list[str] = []
    for segment in _split_title_segments(title_part):
        lines.extend(_wrap_text(draw, segment, f_title, max_text_w))

    curr_y = int(h * 0.03)
    title_line_spacing = int(title_sz * 0.7)
    title_stroke = max(4, int(title_sz * cfg.title_stroke_pct))

    for line in lines:
        if cfg.shadow_offset > 0:
            draw.text(
                (margin + cfg.shadow_offset, curr_y + cfg.shadow_offset),
                line,
                font=f_title,
                fill=(0, 0, 0, 255),
            )
        draw.text(
            (margin, curr_y),
            line,
            font=f_title,
            fill=(255, 255, 255, 255),
            stroke_width=title_stroke,
            stroke_fill=(0, 0, 0, 255),
        )
        bb = draw.textbbox((0, 0), line, font=f_title)
        curr_y += int(bb[3] - bb[1]) + title_line_spacing

    # --- Teacher: bottom-center ---
    if teacher:
        teacher_sz = max(24, int(h * cfg.teacher_size_pct))
        f_teacher = _load_font(teacher_sz, cfg.font_path)
        teacher_stroke = max(2, int(teacher_sz * cfg.title_stroke_pct))
        bb = draw.textbbox((0, 0), teacher, font=f_teacher)
        tw = int(bb[2] - bb[0])
        th = int(bb[3] - bb[1])
        tx = (w - tw) // 2
        ty = h - th - margin
        if cfg.shadow_offset > 0:
            draw.text(
                (tx + cfg.shadow_offset, ty + cfg.shadow_offset),
                teacher,
                font=f_teacher,
                fill=(0, 0, 0, 255),
            )
        draw.text(
            (tx, ty),
            teacher,
            font=f_teacher,
            fill=(255, 255, 255, 255),
            stroke_width=teacher_stroke,
            stroke_fill=(0, 0, 0, 255),
        )

    img.convert("RGB").save(img_path, "JPEG", quality=95)


_FONTS_PER_PAGE = 40


def _font_supports_script(font_path: Path, test_chars: str, size: int = 24) -> bool:
    """Return True only if the font has real glyphs for the given chars (not all-same .notdef boxes)."""
    try:
        font = ImageFont.truetype(str(font_path), size)
        widths = [int(font.getlength(c)) for c in test_chars]
        if all(w == 0 for w in widths):
            return False
        return len(set(widths)) > 1
    except Exception:
        return False


def _font_supports_cyrillic(font_path: Path, size: int = 24) -> bool:
    return _font_supports_script(font_path, "АБВГДЕ", size)


def _font_supports_latin(font_path: Path, size: int = 24) -> bool:
    return _font_supports_script(font_path, "ABCDEFij", size)


def generate_font_preview(output_path: Path, cfg: OverlayCfg, lang: str) -> None:
    font_dirs = [
        Path("/System/Library/Fonts"),
        Path("/System/Library/Fonts/Supplemental"),
        Path("/Library/Fonts"),
        Path("~/Library/Fonts").expanduser(),
    ]

    font_paths: list[Path] = []
    for d in font_dirs:
        if d.exists():
            font_paths.extend(d.glob("**/*.tt[cf]"))
            font_paths.extend(d.glob("**/*.otf"))

    font_paths = sorted(list(set(font_paths)), key=lambda p: p.name.lower())

    skip_substrings = [
        "Braille",
        "NotoSans",
        "NotoSerif",
        "STIX",
        "Wingdings",
        "Webdings",
        "Symbol",
        "Dingbat",
        "LastResort",
    ]

    usable_fonts: list[Path] = []
    for p in font_paths:
        if any(sub in p.name for sub in skip_substrings):
            continue
        usable_fonts.append(p)

    if not usable_fonts:
        pr.no("No usable fonts found for preview.")
        return

    if lang == "ru":
        pr.green(f"Found {len(usable_fonts)} fonts; filtering for Cyrillic support...")
        usable_fonts = [p for p in usable_fonts if _font_supports_cyrillic(p)]
        pr.green(f"{len(usable_fonts)} fonts support Russian")
    else:
        pr.green(f"Found {len(usable_fonts)} fonts; filtering for Latin support...")
        usable_fonts = [p for p in usable_fonts if _font_supports_latin(p)]
        pr.green(f"{len(usable_fonts)} fonts support English")

    if not usable_fonts:
        pr.no("No Cyrillic-capable fonts found.")
        return

    title_sz = 42
    row_h = title_sz * 4
    w = 1600

    sample_title = (
        "The Development of Mindfulness and Wisdom in Everyday Life | Bhikkhu Devamitto"
        if lang == "en"
        else "Развитие Осознанности и Мудрости в Повседневной Жизни | Бхиккху Дэвамитта"
    )
    sample_teacher = "Bhikkhu Devamitto" if lang == "en" else "Бхиккху Дэвамитта"

    f_num = ImageFont.load_default(size=18)
    f_path_label = ImageFont.load_default(size=13)

    pr.green(f"Rendering {len(usable_fonts)} fonts ({lang})...")

    rows: list[tuple[int, Path, Image.Image]] = []
    for idx, p in enumerate(usable_fonts, 1):
        try:
            f_title = ImageFont.truetype(str(p), title_sz)
            f_teacher = ImageFont.truetype(str(p), 28)
        except Exception:
            continue

        row = Image.new("RGB", (w, row_h), (30, 30, 30))
        draw = ImageDraw.Draw(row)

        draw.text((10, 6), f"#{idx}", font=f_num, fill=(255, 200, 50))
        draw.text((65, 8), str(p), font=f_path_label, fill=(140, 140, 140))
        draw.text((10, 36), sample_title, font=f_title, fill=(255, 255, 255))
        draw.text(
            (10, 36 + title_sz + 6),
            sample_teacher,
            font=f_teacher,
            fill=(200, 200, 200),
        )
        draw.line([(0, row_h - 1), (w, row_h - 1)], fill=(80, 80, 80))

        rows.append((idx, p, row))

    if not rows:
        pr.no("Could not render any fonts.")
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)

    pages = [
        rows[i : i + _FONTS_PER_PAGE] for i in range(0, len(rows), _FONTS_PER_PAGE)
    ]
    stem = f"{output_path.with_suffix('').name}_{lang}"
    env_var = "COVER_RU_FONT_PATH" if lang == "ru" else "COVER_FONT_PATH"

    md_lines: list[str] = [
        f"# Font List ({lang})\n\nCopy the path you want, then set `{env_var}=` in `.env`.\n"
    ]

    for page_idx, page in enumerate(pages, 1):
        page_file = output_path.parent / f"{stem}_{page_idx:02d}.png"
        md_lines.append(f"\n## Page {page_idx} — `{page_file.name}`\n\n")
        for num, p, _ in page:
            md_lines.append(f"{num}. `{p}`\n")

        page_h = row_h * len(page)
        page_img = Image.new("RGB", (w, page_h), (0, 0, 0))
        for i, (_, _, row_img) in enumerate(page):
            page_img.paste(row_img, (0, i * row_h))
        page_img.save(page_file, "PNG")
        pr.yes(f"  Page {page_idx}/{len(pages)} → {page_file.name} ({len(page)} fonts)")

    md_path = output_path.parent / f"font_list_{lang}.md"
    md_path.write_text("".join(md_lines), encoding="utf-8")
    pr.yes(f"Font index → {md_path}")
    pr.green(f"Copy a path from {md_path.name}, then set {env_var}= in .env")


def main() -> None:
    load_dotenv(override=True)
    parser = argparse.ArgumentParser(
        description="Composites text overlays onto existing thumbnail images."
    )
    parser.add_argument("--lang", choices=["ru", "en"], default="en")
    parser.add_argument("--folder", help="Optional subfolder name override")
    parser.add_argument("--review-file", type=Path, help="Override review file path")
    parser.add_argument("--input-dir", type=Path, help="Source thumbnail directory")
    parser.add_argument("--output-dir", type=Path, help="Destination for cover images")
    parser.add_argument("--dry-run", action="store_true", help="Do not write anything")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of talks")
    parser.add_argument(
        "--list-fonts", action="store_true", help="Generate font preview sheet and exit"
    )
    parser.add_argument(
        "--created-log",
        type=str,
        default=None,
        help="Path to a file where created cover paths are appended (one per line).",
    )
    parser.add_argument(
        "--source-log",
        type=Path,
        help="Only process review sources listed in this log.",
    )
    parser.add_argument(
        "--title-override",
        type=str,
        default=None,
        help="Use this exact string as the cover title instead of reading from the review file.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Generate covers even when YouTube history marks thumbnails handled.",
    )

    args = parser.parse_args()
    source_filter = read_source_filter(args.source_log)
    cfg = load_overlay_cfg()
    if args.lang == "ru" and cfg.ru_font_path:
        cfg.font_path = cfg.ru_font_path

    if args.list_fonts:
        generate_font_preview(Path("temp/font_preview.jpg"), cfg, args.lang)
        return

    folder_name = args.folder if args.folder is not None else ""
    review_path = args.review_file or Path(
        f"reviews/{LANG_TO_FOLDER[args.lang]}_review.md"
    )
    input_dir = args.input_dir or Path(f"output/thumbnails/{folder_name}")
    output_dir = args.output_dir or Path(f"output/covers/{folder_name}")

    if not review_path.exists():
        pr.no(f"Review file not found: {review_path}")
        return

    talks = parse_review(review_path)
    talks = [
        talk
        for talk in talks
        if source_matches_filter(talk.get("source", ""), source_filter)
    ]
    if args.limit > 0:
        talks = talks[: args.limit]

    history = load_nested_history(HISTORY_PATH, args.lang)
    if not args.force:
        talks = [
            talk
            for talk in talks
            if not (
                (entry := get_uploaded_history_entry(history, f"{talk['source']}.mp4"))
                and entry.get("thumbnail_set") is True
            )
        ]

    import shutil

    skipped = 0
    created = 0
    errors = 0

    pr.green_title(f"Generating covers for {folder_name} ({len(talks)} talks)")

    for talk in talks:
        source = talk["source"]
        out_path = output_dir / f"{source}.jpg"

        if out_path.exists():
            skipped += 1
            continue

        in_path = input_dir / f"{source}.jpg"
        if not in_path.exists():
            pr.amber(f"  Source not found: {source}")
            errors += 1
            continue

        if in_path.stat().st_size < 1024 * 10 and not (
            args.dry_run and is_pipeline_dry_run()
        ):
            pr.amber(f"  Source too small (broken?): {source}")
            errors += 1
            continue

        if args.dry_run:
            pr.white(f"  [DRY RUN] {in_path} → {out_path}")
            if is_pipeline_dry_run():
                create_stub(out_path)
            continue

        title = args.title_override or talk["title"]

        pr.green(f"  Processing: {source}")

        output_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(in_path, out_path)
        add_text_overlay(out_path, title, cfg)
        if args.created_log:
            with open(args.created_log, "a") as log_f:
                log_f.write(str(out_path) + "\n")
        pr.yes(f"  Created: {out_path.name}")
        created += 1

    pr.yes(f"Done: {created} created, {skipped} skipped, {errors} errors")


if __name__ == "__main__":
    main()
