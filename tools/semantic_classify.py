"""LLM-based classification of semantic evaluation findings (TP-fix / TP-defer / FP)."""

import concurrent.futures
import json
import re
import unicodedata
from pathlib import Path

from tools.printer import printer as pr
from tools.provider import build_cacheable_contents, generate_with_timeout


class ClassificationError(RuntimeError):
    """Raised when a classification batch cannot be evaluated safely."""


def _findings_to_text(findings: list[dict[str, str]]) -> str:
    """Render findings as a numbered text block for the LLM input."""
    lines: list[str] = []
    for i, item in enumerate(findings):
        lines.append(f"### Finding {i + 1}")
        lines.append(f"Passage: {item.get('passage', '')}")
        context = item.get("context", "")
        if context:
            lines.append(f"Context: {context}")
        lines.append(f"Issue: {item.get('issue', '')}")
        lines.append(f"Suggestion: {item.get('suggestion', '')}")
        lines.append("")
    return "\n".join(lines)


def build_classification_instruction(
    carried_patterns: str,
    reference_md: str,
) -> str:
    """Build the system instruction for semantic finding classification."""
    instruction = (
        "You are an expert Dhamma transcript reviewer. Your task is to classify "
        "semantic evaluation findings as TP-fix, TP-defer, or FP.\n\n"
        "DEFINITIONS:\n"
        "- TP-fix: True positive, confident fix. Every word in the correction has direct phonetic "
        "correspondence to a word in the source passage. Single-word and multi-word corrections "
        "both allowed when phonetic basis holds for each word. "
        "Example: 'Bhatimokha' -> 'Pāṭimokkha' is direct phonetic match -> TP-fix.\n"
        "- TP-defer: True positive, but needs manual review. Multi-word phrase or compound-term "
        "reconstructions that rely on semantic/contextual guessing rather than phonetic match. "
        "Also: any finding where you are unsure or the fix is plausible but not certain.\n"
        "- FP: False positive. The flagged word/phrase could have been intentionally said by "
        "a Dhamma teacher in context. No change needed.\n\n"
        "PHONETIC COVERAGE RULE:\n"
        "Tag TP-fix only when EVERY word in the correction has a direct phonetic basis in the "
        "original passage — meaning you can hear how the speaker's pronunciation of that passage "
        "word could produce the correction word. Multi-word corrections are allowed when this "
        "condition holds for EACH word.\n"
        "Tag TP-defer when:\n"
        "- ANY correction word introduces meaning with no phonetic basis in the passage (semantic invention)\n"
        "- The correction requires contextual or doctrinal guessing beyond phonetics\n"
        "- The passage is severely garbled with no word-level correspondence\n"
        "- You are unsure\n"
        "Examples:\n"
        "- TP-fix: 'pasta' → 'vassa' (direct phonetic match)\n"
        "- TP-fix: 'tight edition' → 'Thai tradition' (each word maps phonetically)\n"
        "- TP-fix: 'bigger Buddha' → 'Bhikkhu Bodhi' (proper name compound entity)\n"
        "- TP-defer: 'going to be honest' → 'mano, viññāṇa' (invention — no phonetic basis)\n\n"
        "CONTEXT:\n"
        "Always read each finding's Context field before classifying. The isolated passage "
        "can be misleading -- the surrounding 1-2 sentences often reveal whether the flagged "
        "text makes sense in context.\n\n"
    )

    if carried_patterns:
        instruction += (
            "CARRIED PATTERNS (known false-positive / true-positive patterns from prior sessions):\n"
            f"{carried_patterns}\n\n"
        )

    if reference_md:
        instruction += (
            "REFERENCE (known error patterns and DO-NOT-FLAG rules):\n"
            f"{reference_md}\n\n"
        )

    instruction += (
        "OUTPUT: Return ONLY a valid JSON array. Each item must have exactly these keys:\n"
        '  {"passage": "exact quoted passage", "classification": "TP-fix"|"TP-defer"|"FP", '
        '"reason": "one-line concise reason"}\n'
        "No other text outside the JSON."
    )
    return instruction


def classify_findings(
    findings: list[dict[str, str]],
    instruction: str,
) -> list[dict[str, str]]:
    """Classify findings via LLM. Returns list of {passage, classification, reason} dicts."""
    if not findings:
        return []

    input_text = _findings_to_text(findings)
    try:
        result = generate_with_timeout(
            contents=build_cacheable_contents(input_text),
            system_instruction=instruction,
        )
        if not result or not result.strip():
            raise ClassificationError("empty response from LLM")

        json_str = result.strip()
        if json_str.startswith("```json"):
            json_str = json_str[7:].strip()
        if json_str.endswith("```"):
            json_str = json_str[:-3].strip()

        items = json.loads(json_str)
    except ClassificationError:
        raise
    except concurrent.futures.TimeoutError as exc:
        raise ClassificationError("timeout") from exc
    except json.JSONDecodeError as exc:
        raise ClassificationError(f"invalid JSON: {exc}") from exc
    except Exception as exc:
        raise ClassificationError(f"request failed: {exc}") from exc

    if not isinstance(items, list):
        raise ClassificationError("classification response JSON was not a list")

    classified: list[dict[str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            raise ClassificationError("classification response item was not an object")
        classified.append({str(key): str(value) for key, value in item.items()})
    return classified


def parse_report(report_path: Path) -> list[dict[str, str]]:
    """Parse a semantic evaluation report and return a list of finding dicts.

    Parses the format written by scripts/evaluate_semantic.py lines ~176-192:
    ## Passage
    > quoted text
    **Context:** ...
    **Issue:** ...
    **Suggestion:** ...
    ---
    """
    text = report_path.read_text(encoding="utf-8")
    findings: list[dict[str, str]] = []

    blocks = re.split(r"\n## Passage\n", text)
    for block in blocks[1:]:  # skip header before first ## Passage
        finding: dict[str, str] = {}

        passage_match = re.search(r">\s*(.+?)(?:\n\n|\n\*\*|\Z)", block, re.DOTALL)
        if passage_match:
            finding["passage"] = passage_match.group(1).strip()

        context_match = re.search(
            r"\*\*Context:\*\*\s*(.+?)(?:\n\n\*\*|\n\n---|\Z)", block, re.DOTALL
        )
        if context_match:
            finding["context"] = context_match.group(1).strip()

        issue_match = re.search(
            r"\*\*Issue:\*\*\s*(.+?)(?:\n\n\*\*|\n\n---|\Z)", block, re.DOTALL
        )
        if issue_match:
            finding["issue"] = issue_match.group(1).strip()

        suggestion_match = re.search(
            r"\*\*Suggestion:\*\*\s*(.+?)(?:\n\n---|\Z)", block, re.DOTALL
        )
        if suggestion_match:
            finding["suggestion"] = suggestion_match.group(1).strip()

        if finding.get("passage"):
            findings.append(finding)

    return findings


def load_carried_patterns(hub_path: Path | None = None) -> str:
    """Load carried patterns tagged [stage: semantic] from enhance-state.md."""
    if hub_path is None:
        hub_path = Path("kamma/enhance/enhance-state.md")

    if not hub_path.exists():
        return ""

    text = hub_path.read_text(encoding="utf-8")

    carried_match = re.search(
        r"##\s+Carried\s+Patterns\s*\n(.*?)(?=\n##\s|\Z)",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if not carried_match:
        return ""

    section = carried_match.group(1)
    lines = section.strip().split("\n")
    matched: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if re.search(
            r"\[(?:stage:\s*semantic|.*?semantic.*?)\]",
            stripped,
            re.IGNORECASE,
        ):
            matched.append(stripped)

    return "\n".join(matched)


def _extract_correction_words(suggestion: str) -> list[str]:
    """Heuristic: extract the proposed correction words from a suggestion string."""
    if not suggestion:
        return []

    arrow = re.search(
        r"""['\u2018\u2019\"]([^'\u2018\u2019\"]+)['\u2018\u2019\"]\s*(?:→|->|-->)\s*['\u2018\u2019\"]([^'\u2018\u2019\"]+)['\u2018\u2019\"]""",
        suggestion,
    )
    if arrow:
        return arrow.group(2).strip().split()

    quotes = re.findall(
        r"['\u2018\u2019]([^'\u2018\u2019]+)['\u2018\u2019]", suggestion
    )
    if len(quotes) >= 2:
        return quotes[-1].strip().split()
    if len(quotes) == 1:
        return quotes[0].strip().split()

    return suggestion.strip().split()


def _is_proper_name(words: list[str], raw_suggestion: str = "") -> bool:
    """Check if a multi-word sequence looks like a proper name (all capitalized, or possessive)."""
    if len(words) <= 1:
        return False
    alpha_words = [w for w in words if w and w[0].isalpha()]
    if not alpha_words:
        return False
    if all(w[0].isupper() for w in alpha_words):
        return True
    # Possessive proper name: first word capitalized + suggestion contains 's
    if alpha_words[0][0].isupper() and (
        "'s" in raw_suggestion or "\u2019s" in raw_suggestion
    ):
        return True
    return False


def is_multi_word_correction(suggestion: str) -> bool:
    """Return True if the suggested correction is multi-word and not a proper name."""
    words = _extract_correction_words(suggestion)
    if len(words) <= 1:
        return False
    if _is_proper_name(words):
        return False
    return True


def enforce_single_word_rule(
    findings: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Deprecated alias — use enforce_phonetic_coverage_rule()."""
    return enforce_phonetic_coverage_rule(findings)


def _normalize_phonetic(word: str) -> str:
    """Lowercase, strip diacritics, strip trailing plural s."""
    word = word.lower()
    word = unicodedata.normalize("NFKD", word)
    word = "".join(c for c in word if not unicodedata.combining(c))
    if word.endswith("s") and len(word) > 3:
        word = word[:-1]
    return word


def _lcs_ratio(a: str, b: str) -> float:
    """Longest common subsequence length divided by max(len(a), len(b))."""
    if not a or not b:
        return 0.0
    m, n = len(a), len(b)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if a[i - 1] == b[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
    return dp[m][n] / max(m, n)


def _extract_passage_words(passage: str) -> list[str]:
    """Lowercase words from passage, punctuation stripped."""
    tokens = passage.split()
    result: list[str] = []
    for t in tokens:
        t = t.strip("'\".,!?;:()[]")
        if t:
            result.append(t.lower())
    return result


def _split_correction_tokens(suggestion: str) -> list[str]:
    """Extract correction words, expanding hyphens, filtering non-alpha tokens."""
    raw = _extract_correction_words(suggestion)
    tokens: list[str] = []
    for w in raw:
        tokens.extend(w.split("-"))
    tokens = [re.sub(r"[,;:\.]+$", "", t) for t in tokens]
    return [t for t in tokens if re.search(r"[a-zA-Z]", t)]


def _consonant_skeleton(word: str) -> str:
    """Return only the consonant characters (a-z minus aeiou)."""
    return re.sub(r"[aeiou]", "", word)


def _has_phonetic_basis(correction_word: str, passage_words: list[str]) -> bool:
    """Return True if correction_word has consonant-skeleton LCS ratio >= 0.30 with any passage word."""
    cw = _normalize_phonetic(correction_word)
    if len(cw) <= 2:
        return True  # short tokens always allowed
    if not passage_words:
        return True  # empty passage — conservative, allow
    # If all passage words are very short, don't attempt phonetic matching
    if all(len(_normalize_phonetic(pw)) <= 2 for pw in passage_words):
        return True
    cw_consonants = _consonant_skeleton(cw)
    if len(cw_consonants) <= 1:
        return True  # very few consonant skeletons pass
    best = max(
        _lcs_ratio(cw_consonants, _consonant_skeleton(_normalize_phonetic(pw)))
        for pw in passage_words
    )
    return best >= 0.30


def enforce_phonetic_coverage_rule(
    findings: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Downgrade TP-fix to TP-defer when any correction word has no phonetic basis in passage."""
    result: list[dict[str, str]] = []
    for finding in findings:
        if finding.get("classification") != "TP-fix":
            result.append(finding)
            continue
        suggestion = finding.get("suggestion", "")
        passage = finding.get("passage", "")
        tokens = _split_correction_tokens(suggestion)
        if _is_proper_name(tokens, suggestion):
            result.append(finding)
            continue
        passage_words = _extract_passage_words(passage)
        for token in tokens:
            if not _has_phonetic_basis(token, passage_words):
                finding = dict(finding)
                finding["classification"] = "TP-defer"
                existing = finding.get("reason", "")
                finding["reason"] = (
                    f"{existing} [DOWNGRADED: no phonetic basis for '{token}']".strip()
                )
                break
        result.append(finding)
    return result


def format_compact(findings: list[dict[str, str]]) -> str:
    """Render findings as compact pipe-delimited lines matching subagent return format."""
    lines: list[str] = []
    for item in findings:
        passage = item.get("passage", "").replace("|", "\\|")
        classification = item.get("classification", "")
        reason = item.get("reason", "").replace("|", "\\|")
        lines.append(f"{passage} | {classification} | {reason}")
    return "\n".join(lines)


def fetch_full_context(passage: str, file_path: Path) -> str:
    """Return the full Whisper timestamp block containing the passage."""
    try:
        text = file_path.read_text(encoding="utf-8")
    except OSError:
        pr.amber(
            f"Context not found for passage: '{passage[:50]}...' in {file_path.name}"
        )
        return ""

    idx = text.lower().find(passage.lower())
    if idx == -1:
        pr.amber(
            f"Context not found for passage: '{passage[:50]}...' in {file_path.name}"
        )
        return ""

    marker_pattern = re.compile(r"\n\[(\d+)\.(\d+)\]\s")

    before = text[:idx]
    prev_match = None
    for m in marker_pattern.finditer(before):
        prev_match = m

    after = text[idx:]
    next_match = marker_pattern.search(after[len(passage) :])

    if prev_match is None:
        pr.amber(
            f"No timestamp marker before passage: '{passage[:50]}...' in {file_path.name}"
        )
        return ""

    start = prev_match.end()

    if next_match is not None:
        end = idx + len(passage) + next_match.start()
    else:
        end = len(text)

    return text[start:end].strip()


def resolve_transcript(report_path: Path, base_dir: Path | None = None) -> Path | None:
    """Resolve a semantic report to its corrected transcript file."""
    from pathlib import Path as _Path

    if base_dir is None:
        base_dir = _Path("output/corrected_pali/interview")

    stem = report_path.stem
    nfc_stem = unicodedata.normalize("NFC", stem)

    date_match = re.search(r"(\d{2}-\d{2}-\d{2})", nfc_stem)
    if not date_match:
        pr.amber(
            f"No date pattern found in report name: {report_path.name} — pro tier skipped"
        )
        return None
    date_pattern = date_match.group(1)

    suffix_match = re.search(
        r"(?:MN\d+|feedback|-\d+)(?:\s*-\d+)*$", nfc_stem[date_match.end() :].strip()
    )
    special_suffix = suffix_match.group(0).strip() if suffix_match else ""

    if not base_dir.exists():
        pr.amber(f"Transcript directory not found: {base_dir}")
        return None

    candidates: list[Path] = []
    for candidate in base_dir.iterdir():
        if not candidate.is_file() or candidate.suffix != ".md":
            continue
        nfc_name = unicodedata.normalize("NFC", candidate.stem)
        cand_date = re.search(r"(\d{2}-\d{2}-\d{2})", nfc_name)
        if not cand_date:
            continue
        if cand_date.group(1) != date_pattern:
            continue
        cand_suffix_match = re.search(
            r"(?:MN\d+|feedback|-\d+)(?:\s*-\d+)*$",
            nfc_name[cand_date.end() :].strip(),
        )
        cand_suffix = cand_suffix_match.group(0).strip() if cand_suffix_match else ""
        if cand_suffix == special_suffix:
            candidates.append(candidate)

    if len(candidates) == 0:
        pr.amber(
            f"No transcript found for report: {report_path.name} — pro tier skipped for this file"
        )
        return None
    elif len(candidates) > 1:
        names = ", ".join(c.name for c in candidates)
        pr.amber(
            f"Ambiguous transcript match for {report_path.name}: {names} — pro tier skipped for this file"
        )
        return None
    return candidates[0]
