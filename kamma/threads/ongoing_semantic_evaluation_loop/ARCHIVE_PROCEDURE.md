# Archive Procedure — Semantic Evaluation Loop

To keep agent context lean and performance high, follow this procedure at the end of every session where Session N-2 is being moved to the handoff archive.

## When to Archive
- Run this during the **Handoff Maintenance** phase (Session End).
- Target files: `manual_corrections.md` and `ledger.json`.
- Condition: If `manual_corrections.md` contains more than 2 active sessions (N, N-1), move the oldest session(s) to archive.

## Procedure: manual_corrections.md

1. **Identify Session Boundaries:**
   - Active sessions are the current (N) and previous (N-1).
   - Any session N-2 or older is a candidate for archiving.

2. **Move to Archive:**
   - Open `manual_corrections.md`.
   - Copy the content of Session N-2 and older.
   - Append this content to `archive/manual_corrections_archive.md` under a header for that session.
   - Delete the archived content from `manual_corrections.md`.

3. **Update Hot List:**
   - Scan the active sessions (N, N-1) for unresolved/deferred items.
   - Update the "## Unresolved Items (Hot List)" section at the top of `manual_corrections.md`.
   - Remove any items that were resolved/applied in the current session.
   - Format: `- Item (Session X) — status: unresolved`.

## Procedure: ledger.json

1. **Prune Stale Entries:**
   - Keep entries for the active sessions (N, N-1).
   - Remove entries for reports that are marked "clean" or have been fully processed in older sessions.
   - Ensure `pending_next_session` is preserved (if not empty).

2. **Clean Summaries:**
   - Keep the summaries for active sessions (N, N-1).
   - Remove old session summaries.

## Handoff Integration Checklist

Add these steps to the "⚠️ EVERY SESSION END — Handoff Maintenance Checklist" in `handoff.md`:

```markdown
- [ ] Archive Session [N-2] from `manual_corrections.md` to `archive/manual_corrections_archive.md`
- [ ] Update "Hot List" in `manual_corrections.md` with current unresolved items
- [ ] Prune `ledger.json` (remove entries older than 2 sessions or marked "clean")
```

## Example
If current session is **Session 12**:
- Keep Sessions 12 and 11 in `manual_corrections.md`.
- Move Session 10 (and any older) to `archive/manual_corrections_archive.md`.
- Keep Session 12 and 11 entries in `ledger.json`.
