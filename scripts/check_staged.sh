#!/bin/sh
# Run before every commit. Stops the commit if the staged changes contain
# image/video files or something that looks like a real Kling ProduceID
# (a 15-digit number starting 31..39: real IDs began at 2886 in Sep 2025, were 3234
# in Oct 2026 and keep growing about 86,400 per day, so a fixed prefix goes stale).
# Made-up IDs in this repo start with 30 (e.g. 3000000...), so they pass.
status=0
files=$(git diff --cached --name-only --diff-filter=ACMR)
bad_files=$(printf '%s\n' "$files" | grep -iE '\.(png|jpe?g|webp|gif|heic|mp4|mov|m4v|avi|mkv)$')
if [ -n "$bad_files" ]; then
    echo "Staged media files (not allowed):"; echo "$bad_files"; status=1
fi
ID_RE='(^|[^0-9])3[1-9][0-9]{13}([^0-9]|$)'
if git diff --cached -U0 | grep -E '^\+' | grep -vE '^\+\+\+' | grep -qE "$ID_RE"; then
    echo "Staged diff contains a real-looking ProduceID (15 digits starting 31-39):"
    git diff --cached -U0 | grep -E '^\+' | grep -vE '^\+\+\+' | grep -nE "$ID_RE" | cut -c1-160; status=1
fi
[ $status -eq 0 ] && echo "check_staged: OK (no media files, no real-looking IDs)"
exit $status
