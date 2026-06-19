"""Shared language-code → pipeline-folder mapping for transcription and YouTube scripts."""

LANG_TO_FOLDER: dict[str, str] = {"ru": "russian", "en": "english"}


def lang_folder(lang: str | None) -> str:
    """Return the pipeline folder for a language code, defaulting to English."""
    return LANG_TO_FOLDER.get(lang or "en", "english")
