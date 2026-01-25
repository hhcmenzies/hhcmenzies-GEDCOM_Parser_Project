#!/usr/bin/env bash
set -euo pipefail

PROJ="$HOME/GEDCOM_Parser_Project"
INVROOT="$PROJ/inventory"
TS="$(date +%Y%m%d_%H%M%S)"
OUT="$INVROOT/$TS"

mkdir -p "$OUT" "$INVROOT/legacy/old"

# If inventory outputs already exist, move them to legacy/old (keep prior snapshots tidy)
find "$INVROOT" -maxdepth 1 -type d -name "20*" -not -name "$TS" -print0 \
  | xargs -0 -I{} bash -c 'bn="$(basename "{}")"; mv "{}" "'"$INVROOT"'/legacy/old/$bn"' || true

# Core file inventory (path, size, mtime)
( cd "$PROJ" && find . -type f -printf '%TY-%Tm-%Td %TH:%TM:%TS\t%s\t%p\n' | sort ) \
  > "$OUT/files.tsv"

# Directory sizes
( cd "$PROJ" && du -ah . | sort -hr ) > "$OUT/du.txt"

# Tree view (if tree exists)
if command -v tree >/dev/null 2>&1; then
  ( cd "$PROJ" && tree -a -I '.git|node_modules|__pycache__|.venv|venv' ) > "$OUT/tree.txt"
else
  echo "tree not installed" > "$OUT/tree.txt"
fi

# Git status + last commits (if it's a git repo)
if [ -d "$PROJ/.git" ]; then
  ( cd "$PROJ" && git status --porcelain=v1 ) > "$OUT/git_status.txt"
  ( cd "$PROJ" && git log -n 30 --date=iso --pretty=format:'%ad %h %s' ) > "$OUT/git_log_30.txt"
  ( cd "$PROJ" && git remote -v ) > "$OUT/git_remotes.txt"
fi

# Hashes for key artifacts (fast-ish; adjust patterns as needed)
( cd "$PROJ" && find . -type f \( -name '*.json' -o -name '*.yml' -o -name '*.yaml' -o -name '*.py' -o -name '*.ged' \) -print0 \
  | xargs -0 sha256sum | sort ) > "$OUT/hashes.sha256"

# Create / refresh "latest" symlink
ln -sfn "$OUT" "$INVROOT/latest"

echo "Inventory written to: $OUT"
echo "Latest pointer: $INVROOT/latest"
