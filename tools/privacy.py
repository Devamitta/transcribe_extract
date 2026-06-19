"""Deterministic privacy scanning and replacement helpers for extracted Dhamma text."""

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

from tools.glossary import FAMOUS_TEACHERS, MONASTICS, PLACES

PrivacyCategory = Literal["monastic", "teacher", "place"]

CONTEXT_WINDOW = 60


@dataclass(frozen=True)
class Hit:
    term: str
    category: PrivacyCategory
    context: str
    start: int
    end: int


@dataclass(frozen=True)
class Fix:
    term: str
    category: PrivacyCategory
    replacement: str
    count: int


@dataclass(frozen=True)
class PrivacyTerm:
    term: str
    category: PrivacyCategory


def scan_text(text: str) -> list[Hit]:
    normalized_text = _normalize(text)
    hits: list[Hit] = []

    for privacy_term in _privacy_terms():
        pattern = _term_pattern(privacy_term.term)
        for match in pattern.finditer(normalized_text):
            hits.append(
                Hit(
                    term=privacy_term.term,
                    category=privacy_term.category,
                    context=_context(normalized_text, match.start(), match.end()),
                    start=match.start(),
                    end=match.end(),
                )
            )

    return sorted(hits, key=lambda hit: (hit.start, -len(hit.term)))


def apply_fixes(text: str) -> tuple[str, list[Fix]]:
    fixed_text = _normalize(text)
    fixes: list[Fix] = []

    for privacy_term in sorted(
        _privacy_terms(),
        key=lambda item: len(item.term),
        reverse=True,
    ):
        replacement = _replacement_for(privacy_term)
        pattern = _term_pattern(privacy_term.term)
        fixed_text, count = pattern.subn(replacement, fixed_text)
        if count:
            fixes.append(
                Fix(
                    term=privacy_term.term,
                    category=privacy_term.category,
                    replacement=replacement,
                    count=count,
                )
            )

    return fixed_text, fixes


def _privacy_terms() -> list[PrivacyTerm]:
    terms: list[PrivacyTerm] = []
    seen: set[str] = set()
    source_lists: tuple[tuple[PrivacyCategory, list[str]], ...] = (
        ("monastic", MONASTICS),
        ("teacher", FAMOUS_TEACHERS),
        ("place", PLACES),
    )
    for category, values in source_lists:
        for value in values:
            term = _normalize(value)
            key = term.casefold()
            if not term or key in seen:
                continue
            seen.add(key)
            terms.append(PrivacyTerm(term=term, category=category))
    return terms


def _term_pattern(term: str) -> re.Pattern[str]:
    return re.compile(rf"(?<!\w){re.escape(_normalize(term))}(?!\w)", re.IGNORECASE)


def _replacement_for(term: PrivacyTerm) -> str:
    if term.category in {"monastic", "teacher"}:
        return "a teacher"

    lowered = term.term.casefold()
    monastery_markers = (
        "wat",
        "sanctuary",
        "sasanarakkha",
        "sbs",
        "amaravati",
        "chithurst",
        "bodhinyana",
    )
    if any(marker in lowered for marker in monastery_markers):
        return "a monastery"
    return "another place"


def _context(text: str, start: int, end: int) -> str:
    context_start = max(start - CONTEXT_WINDOW, 0)
    context_end = min(end + CONTEXT_WINDOW, len(text))
    return " ".join(text[context_start:context_end].split())


def _normalize(text: str) -> str:
    return unicodedata.normalize("NFC", text)
