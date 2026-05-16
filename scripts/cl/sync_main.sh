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
