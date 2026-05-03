# Ongoing Loops Handoff Standard

---

## Purpose

This document defines the standard handoff format for all **ongoing/recurring loops** in the Kamma framework. Ongoing loops are threads that remain active across multiple sessions and require special maintenance to keep handoff files readable.

**Note:** This standard applies ONLY to ongoing loops. One-time threads do not use the 2-session maintenance rule.

---

## Standard Handoff Template

Copy this template when creating a new ongoing loop:

```markdown
# Handoff: [Thread Name]

## How to Use This File
Read this before every session. It records what has been attempted, what worked,
what failed, and what patterns are known — so no session repeats prior mistakes.

All archived sessions are in this thread folder `archive/handoff_archive.md`. Only the 2 most recent sessions are kept in this file for quick reference.

---

## ⚠️ EVERY SESSION END — Handoff Maintenance Checklist

Before marking the session complete, run these steps:

- Move session [N-2] from this file to `archive/handoff_archive.md` (keep only sessions [N-1, N])
- Delete old session entries from "Errors, issues, and repeated mistakes" section
- Verify this file contains ONLY the 2 most recent sessions + their errors
- Verify `archive/handoff_archive.md` received the archived session
- Confirm `plan.md` is unchanged (reusable template for next session)

If you skip this, the next session's handoff will be 100+ lines too long. Don't skip.

---

## Session Log

### Session N: YYYY-MM-DD — [Brief description]

- **last_run:** YYYY-MM-DDTHH:MM:SSZ
- **Date:** YYYY-MM-DD
- **Evaluation mode:** [Batch/fresh/pending queue]
- **Files processed:** [description]
- **[Other metadata...]**

**Errors, issues, and repeated mistakes (Session N):**
- [Issues from this session]

---

## Archive Note
All older sessions are in `archive/handoff_archive.md`.
```

---

## Mandatory Sections

All ongoing loop handoff files MUST have:

1. **How to Use This File** — Instructions for reading the file (appears at top)
2. **Maintenance Instructions** — Bullet-point checklist (NOT checkboxes)
3. **Session Log** — The active sessions (≤2)
4. **Errors, issues, and repeated mistakes** — Section for current session errors

---

## Enforcement Guide

### Why 2 Sessions Only?

- **Readability:** A 100+ line handoff overwhelms the next session agent
- **Context Freshness:** Only recent sessions are relevant for task continuity
- **Archive Preservation:** All history is preserved in `archive/handoff_archive.md`

### How to Move a Session to Archive

1. Identify the oldest session in `handoff.md` (e.g., Session N-2 when you have N and N-1)
2. Copy that entire session block (from `### Session N-2:` to its last `-` bullet)
3. Paste into `archive/handoff_archive.md` at the top (newest first)
4. Delete the session block from `handoff.md`
5. Update any references in the Errors section

### When to Clean Up the Errors Section

- After archiving a session, delete its corresponding error entries
- Keep only the current session's errors in the active file
- Old errors are preserved in the archived session block

### Archive File Location

- Path: `<thread>/archive/handoff_archive.md`
- Create the `archive/` folder if it doesn't exist
- Format: Sessions listed newest-first, separated by `---`

---

## Compliance Status

| Thread | Sessions | ≤2? | How to Use | Maintenance | Errors | Archive |
|--------|----------|-----|------------|-------------|--------|---------|
| semantic_evaluation_loop | 2 | ✓ | ✓ | ✓ | ✓ | ✓ |
| pali_correction_feedback | 1 | ✓ | ✓ | ✓ | ✓ | ✓ |
| transcription_feedback | 2 | ✓ | ✓ | ✓ | ✓ | ✓ |
| extract_quality | 2 | ✓ | ✓ | ✓ | ✓ | ✓ |
| polish_quality | 0 | ✓ | ✓ | ✓ | ✓ | ✓ |

**Last verified:** 2026-04-30

---

## Creating a New Ongoing Loop

1. Create thread folder under `kamma/threads/`
2. Create `handoff.md` using the template above
3. Create `archive/handoff_archive.md` with `## Archived Sessions` header
4. Run `/kamma:1-plan` to create the thread plan

The maintenance checklist in the template will ensure the thread stays compliant automatically.