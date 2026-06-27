"""LLM-based classification of semantic evaluation findings (TP-fix / TP-defer / FP)."""

import concurrent.futures
import json
import re
from pathlib import Path

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
        "- TP-fix: True positive, confident fix. The correction is a SINGLE WORD or a PROPER NAME "
        "with direct, verifiable phonetic correspondence to the source audio garble. "
        "Example: 'Bhatimokha' -> 'Pāṭimokkha' is single-word direct phonetic match -> TP-fix.\n"
        "- TP-defer: True positive, but needs manual review. Multi-word phrase or compound-term "
        "reconstructions that rely on semantic/contextual guessing rather than phonetic match. "
        "Also: any finding where you are unsure or the fix is plausible but not certain.\n"
        "- FP: False positive. The flagged word/phrase could have been intentionally said by "
        "a Dhamma teacher in context. No change needed.\n\n"
        "CRITICAL SINGLE-WORD RULE:\n"
        "Only tag a finding TP-fix if the correction is a SINGLE WORD or a PROPER NAME "
        "(capitalized, single entity like a person/monastery name). Multi-word phrase or "
        "compound-term reconstructions must be tagged TP-defer, never TP-fix -- regardless of "
        "how plausible the meaning looks. A proper name may consist of multiple words only if "
        "it is a well-known compound proper name (e.g. 'Ajahn Brahm', 'Wat Pah Nanachat').\n\n"
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
        r"['\u2018\u2019]([^'\u2018\u2019]+)['\u2018\u2019]\s*(?:→|->|-->)\s*['\u2018\u2019]([^'\u2018\u2019]+)['\u2018\u2019]",
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


def _is_proper_name(words: list[str]) -> bool:
    """Check if a multi-word sequence looks like a proper name (all capitalized)."""
    alpha_words = [w for w in words if w and w[0].isalpha()]
    if not alpha_words:
        return False
    return all(w[0].isupper() for w in alpha_words)


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
    """Deterministic downgrade: multi-word TP-fix suggestions forced to TP-defer."""
    downgraded: list[dict[str, str]] = []
    for finding in findings:
        classification = finding.get("classification", "")
        suggestion = finding.get("suggestion", "")
        if classification == "TP-fix" and is_multi_word_correction(suggestion):
            finding = dict(finding)
            finding["classification"] = "TP-defer"
            existing = finding.get("reason", "")
            finding["reason"] = (
                f"{existing} [DOWNGRADED: multi-word correction]".strip()
            )
        downgraded.append(finding)
    return downgraded


def format_compact(findings: list[dict[str, str]]) -> str:
    """Render findings as compact pipe-delimited lines matching subagent return format."""
    lines: list[str] = []
    for item in findings:
        passage = item.get("passage", "").replace("|", "\\|")
        classification = item.get("classification", "")
        reason = item.get("reason", "").replace("|", "\\|")
        lines.append(f"{passage} | {classification} | {reason}")
    return "\n".join(lines)
