# Plan: Reviews Branch Sync

## Architecture Decisions
- **Outbound direction only**: personal/reviews → master → GitHub. Master never has
  commits that didn't originate on personal/reviews. No inbound sync needed.
- **Cherry-pick per commit**: preserves individual commit messages and history on master.
  Reviews-only commits are skipped. Mixed commits land on master with reviews/ stripped.
  No commit naming convention required — filter is file-based.
- **Tracking via `sync-point` tag**: after each successful sync, script updates a local
  git tag `sync-point` to the current personal/reviews HEAD. Next run cherry-picks
  commits after that tag. This avoids `git merge-base` which breaks after cherry-picks
  (cherry-picked commits have new SHAs, so merge-base doesn't advance).
- **No back-merge**: master changes never need to flow back to personal/reviews.
- **All code lives on master first**: templates + .gitattributes + sync script committed
  on master, then a one-time bootstrap merge brings them to personal/reviews.

---

## Phase 1: Create personal/reviews branch

### Task 1.1 — Create branch from current master
Real review data in reviews/ carries over automatically.
```bash
git checkout -b personal/reviews
```
[x] verify: `git rev-parse --abbrev-ref HEAD` prints `personal/reviews`
[x] verify: `reviews/english_review.md` contains real talk entries

### Task 1.2 — Switch back to master
```bash
git checkout master
```
[x] verify: `git rev-parse --abbrev-ref HEAD` prints `master`

---

## Phase 2: All master changes (templates + safeguard + script)

### Task 2.1 — Replace `reviews/english_review.md` with template
Overwrite with exact content:
```
# Tims Audio Metadata Review
Review and edit the suggested titles and descriptions below.
The export script will use this file as the source of truth.

<!-- template only — real data lives on personal/reviews branch -->
```
[x] verify: 5 lines, no talk entries

### Task 2.2 — Replace `reviews/russian_review.md` with template
Overwrite with exact content:
```
# Russian Audio Metadata Review
Fill in the Recording Date (DD-MM-YYYY) for each talk before exporting.
Review and edit the suggested titles and descriptions.

<!-- template only — real data lives on personal/reviews branch -->
```
[x] verify: 5 lines, no talk entries

### Task 2.3 — Create `.gitattributes`
Create `/Users/deva/Documents/dps/transcribe_extract/.gitattributes`:
```
reviews/*.md merge=ours
```
[x] verify: file exists with that single line

### Task 2.4 — Write `scripts/cl/sync_main.sh`
Create `/Users/deva/Documents/dps/transcribe_extract/scripts/cl/sync_main.sh`:

```bash
#!/usr/bin/env bash
# Syncs personal/reviews commits to origin/master, stripping reviews/ from every commit.
#
# Run from personal/reviews branch. Reviews-only commits are skipped.
# Mixed commits (code + reviews/) land on master with reviews/ stripped.
# Tracking: git tag 'sync-point' is updated after each successful sync.

set -euo pipefail

PERSONAL_BRANCH="personal/reviews"
MASTER_BRANCH="master"
PUBLIC_REMOTE="${PUBLIC_REMOTE:-origin}"
SYNC_TAG="sync-point"

# 1. Verify branch
current=$(git rev-parse --abbrev-ref HEAD)
if [[ "$current" != "$PERSONAL_BRANCH" ]]; then
    printf "ERROR: Must be on '%s'. Currently on '%s'.\n" "$PERSONAL_BRANCH" "$current" >&2
    exit 1
fi

# 2. Find commits to sync (since last sync-point tag)
if git rev-parse "$SYNC_TAG" &>/dev/null; then
    base=$(git rev-parse "$SYNC_TAG")
else
    printf "ERROR: No '%s' tag found. Run bootstrap first.\n" "$SYNC_TAG" >&2
    exit 1
fi

mapfile -t commits < <(git log --reverse --format="%H" "$base..$PERSONAL_BRANCH")

if [[ ${#commits[@]} -eq 0 ]]; then
    printf "Already in sync — nothing to transfer.\n"
    exit 0
fi

printf "Found %d commit(s) since last sync.\n" "${#commits[@]}"

# 3. Switch to master and cherry-pick
git checkout "$MASTER_BRANCH"

synced=0
skipped=0
for sha in "${commits[@]}"; do
    msg=$(git log -1 --format="%s" "$sha")

    # Skip commits that only touch reviews/
    non_review=$(git diff-tree --no-commit-id -r --name-only "$sha" \
        | grep -v '^reviews/' || true)
    if [[ -z "$non_review" ]]; then
        printf "  skip  %.7s  %s\n" "$sha" "$msg"
        skipped=$((skipped + 1))
        continue
    fi

    # Cherry-pick without committing
    if ! git cherry-pick --no-commit "$sha" 2>/dev/null; then
        printf "ERROR: Cherry-pick conflict on %.7s (%s).\n" "$sha" "$msg" >&2
        printf "Resolve conflicts on master manually, then re-run.\n" >&2
        git cherry-pick --abort 2>/dev/null || true
        git checkout "$PERSONAL_BRANCH"
        exit 1
    fi

    # Strip reviews/ — restore template version from master HEAD
    git checkout HEAD -- reviews/ 2>/dev/null || true

    # Skip if nothing left to commit (changes were already applied)
    if git diff --cached --quiet; then
        printf "  skip  %.7s  %s  (already applied)\n" "$sha" "$msg"
        git reset HEAD -- . 2>/dev/null || true
        skipped=$((skipped + 1))
        continue
    fi

    # Commit preserving original message and author
    git commit -C "$sha" --reset-author
    printf "  sync  %.7s  %s\n" "$sha" "$msg"
    synced=$((synced + 1))
done

# 4. Push master to GitHub
if [[ $synced -gt 0 ]]; then
    git push "$PUBLIC_REMOTE" "$MASTER_BRANCH"
fi

# 5. Update sync-point tag to current personal/reviews HEAD
git checkout "$PERSONAL_BRANCH"
git tag -f "$SYNC_TAG" HEAD

printf "\nDone. Transferred %d commit(s) to %s/%s, skipped %d (reviews only).\n" \
    "$synced" "$PUBLIC_REMOTE" "$MASTER_BRANCH" "$skipped"
```

[x] verify: file exists at `scripts/cl/sync_main.sh`

### Task 2.5 — Make executable
```bash
chmod +x scripts/cl/sync_main.sh
```
[x] verify: execute bit set

### Task 2.6 — Syntax and lint
```bash
bash -n scripts/cl/sync_main.sh
shellcheck scripts/cl/sync_main.sh
```
[x] verify: both exit 0, no warnings

### Task 2.7 — Stage all master changes
```bash
git add reviews/english_review.md reviews/russian_review.md \
    .gitattributes scripts/cl/sync_main.sh
```
[x] verify: `git diff --cached --stat` shows all four files

### Task 2.8 — Prepare master commit message (present for manual execution)
```
feat: reviews branch setup — templates, merge safeguard, sync script
```
[~] verify: commit message ready (pending manual commit)

---

## Phase 3: Bootstrap personal/reviews

### Task 3.1 — Switch to personal/reviews
```bash
git checkout personal/reviews
```
→ verify: `git rev-parse --abbrev-ref HEAD` prints `personal/reviews`

### Task 3.2 — Merge master to get .gitattributes and script
```bash
git merge --no-commit --no-ff master
```
reviews/ will conflict (master=template, personal=real data). Continue:
```bash
git checkout HEAD -- reviews/
git add reviews/
```
→ verify: `git status` shows reviews/ staged with no conflict markers
→ verify: real talk entries still in reviews/english_review.md

### Task 3.3 — Prepare personal/reviews commit message (present for manual execution)
```
chore: merge master setup into personal/reviews, reviews preserved
```

### Task 3.4 — Set initial sync-point tag (after commit is made manually)
```bash
git tag sync-point HEAD
```
This marks where syncing begins. The script will only process commits made after this point.
→ verify: `git rev-parse sync-point` returns current HEAD SHA

---

## Phase 4: Verification

### Task 4.1 — Wrong-branch guard test
```bash
git checkout master
bash scripts/cl/sync_main.sh
git checkout personal/reviews
```
→ verify: prints `ERROR: Must be on 'personal/reviews'. Currently on 'master'.` exits 1

### Task 4.2 — Already-in-sync test
Run the script immediately after setup (nothing new to sync):
```bash
bash scripts/cl/sync_main.sh
```
→ verify: prints `Already in sync — nothing to transfer.` exits 0

### Task 4.3 — Confirm branch state
```bash
git log --oneline --graph --all -10
```
→ verify: master has templates, personal/reviews has real data, history looks correct
