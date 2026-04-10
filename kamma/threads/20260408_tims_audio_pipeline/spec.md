# Specification: Process Tims Audio Recordings with Reviewable Metadata Export

## Overview

Add a dedicated processing flow for recordings in `audio/tims/`. The pipeline should support folder-specific transcription output, generate reviewable upload title and YouTube upload description suggestions from the resulting transcript markdown files, and then package approved outputs into a dedicated export location.

## What It Should Do

### Folder-aware transcription

- Update `scripts/transcribe.py` so it can run against a specific input folder instead of only top-level `audio/` files.
- Allow the caller to set a specific output folder for transcript markdown files.
- Support the Tims use case where input is `audio/tims/` and output is `output/transcribed/tims/`.
- Preserve the current default behavior for the existing top-level audio flow.
- Continue to skip files that already have transcript output so interrupted runs can resume.

### Tims metadata suggestion extraction

- Create a new script, similar in role to `scripts/extract_dhamma.py`, that reads transcript markdown files from the Tims transcription output.
- Unlike `scripts/extract_dhamma.py`, this new script does not need chunked processing; it should send the full markdown file content with an appropriate prompt.
- For each transcript, generate:
  - a proposed upload title / filename-safe content title
  - a concise YouTube upload description for a static-image video upload
- Save the suggestions into one combined markdown review file that lists, for every source file:
  - original file name
  - suggested title
  - suggested upload description
- The script must also support a single-file testing mode so prompt quality and output format can be checked on one specific transcript before running the full batch.

### Approved export packaging

- After the human approves the proposed names, provide a separate step that renames only generated files based on the approved names.
- Treat the edited combined markdown review file as the source of truth for approved titles and upload descriptions.
- Place approved generated outputs into `output/audio-tims/`.
- Save markdown output that includes each approved title and upload description.
- Save an aggregated markdown file containing all approved titles and upload descriptions together.

## Constraints

- Follow existing project conventions: Python, `Path` usage, type hints, and the existing provider-based content generation path.
- Do not break the current non-Tims transcription flow.
- Keep the approval step explicit; automatic rename/export should not happen before human review.
- Generated filenames must be safe and deterministic enough to use in filesystem output.
- The implementation should work with transcript markdown files generated from the Tims folder, not only with manually supplied single files.
- The metadata generator must support an explicit single-file mode for testing.

## How We Will Know It Is Done

- `scripts/transcribe.py` can run for a custom input folder and custom output folder.
- Running the Tims transcription flow writes transcript markdown files under `output/transcribed/tims/`.
- A new metadata extraction script can process those transcript markdown files and create one combined markdown review document with title and concise YouTube upload description suggestions for each transcript.
- The metadata extraction script can also be run against one specific transcript file for testing.
- The approved export step can rename only generated files and place the approved outputs under `output/audio-tims/`.
- The export step also writes an aggregated markdown file containing all approved titles and upload descriptions.
- The workflow runs automatically until a human verification checkpoint, then pauses for review before rename/export continues.
- The changed Python files satisfy project formatting and linting requirements.

## What Is Not Included

- Renaming original source MP3 files in `audio/tims/`
- Auto-publishing to YouTube or any external platform
- Fully automated approval without a human review checkpoint

## Future Follow-up

- Once this workflow is stable, extract it into a reusable template under `kamma/tims/`.
- Future runs should be able to start from that template, execute automatically through suggestion generation, pause for verification, and resume for rename/export after approval.
