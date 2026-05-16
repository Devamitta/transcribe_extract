# Spec: Reviews Branch Sync

## Overview
All daily work (code + reviews data) happens on the local `personal/reviews` branch.
`reviews/english_review.md` and `reviews/russian_review.md` hold personal talk metadata
that must never reach GitHub. A sync script periodically transfers code commits to
`master` and pushes to GitHub, stripping `reviews/` from every commit.

## Branch model
- `personal/reviews` — local only, default working branch, contains real reviews data
- `master` — GitHub-facing, template-only reviews files, receives synced code commits

## What It Should Do

### Deliverable 1 — Migrate reviews to `personal/reviews`
- Create `personal/reviews` branch from current master (real review data carries over)
- On `master`: replace both review files with empty templates (headers intact, all talk
  entries removed, comment noting real data lives on personal/reviews)
- Commit template versions on master

### Deliverable 2 — `.gitattributes` merge safeguard
Add `reviews/*.md merge=ours` at repo root. One-time per-machine:
`git config --global merge.ours.driver true`.

### Deliverable 3 — `scripts/cl/sync_main.sh` (outbound sync)
Bash script that, when run from `personal/reviews`:
1. Aborts if not on `personal/reviews` or if `sync-point` tag is missing
2. Cherry-picks every commit since the `sync-point` tag onto master:
   - Reviews-only commits → skipped (never reach GitHub)
   - Mixed commits → cherry-picked with `reviews/` stripped
3. Pushes master to `origin`
4. Updates the `sync-point` tag to current personal/reviews HEAD
5. Prints summary (synced N, skipped M)

**Tracking:** the `sync-point` local git tag marks where the last sync ended. Using
`git merge-base` would fail here because cherry-picked commits get new SHAs, so
merge-base never advances. The tag sidesteps this entirely.

**Mixed commits are handled:** code + reviews/ in one commit → only code lands on master.
Commit message preserved as-is. No naming convention needed.

## Assumptions
- `personal/reviews` is local only, never pushed to origin
- Only reviews/ files differ between branches — no other local-only changes on personal
- Template = headers/format preserved, all talk entries removed
- Single developer — no upstream conflicts on non-reviews files expected

## Constraints
- Pure bash/git — no Python
- No `sed`/`awk`

## How We'll Know It's Done
- `personal/reviews` branch exists with real reviews data
- `master` has template-only reviews files
- `.gitattributes` has `reviews/*.md merge=ours` on both branches
- Script passes `bash -n` and `shellcheck`
- Script correctly skips reviews-only commits and strips reviews/ from mixed commits
- Wrong-branch guard exits 1

## What's Not Included
- Pushing `personal/reviews` to any remote
- Automatic scheduling
- Changes to pipeline scripts
