#!/bin/sh
# Run before every commit. Stops the commit if the staged changes contain
# image/video files or something that looks like a real Kling ProduceID
# (15 digits starting with 3234). Made-up IDs in this repo start with 3000.
status=0
files=$(git diff --cached --name-only --diff-filter=ACMR)
bad_files=$(printf '%s\n' "$files" | grep -iE '\.(png|jpe?g|webp|gif|heic|mp4|mov|m4v|avi|mkv)$')
if [ -n "$bad_files" ]; then
    echo "Staged media files (not allowed):"; echo "$bad_files"; status=1
fi
if git diff --cached -U0 | grep -E '^\+' | grep -qE '3234[0-9]{11}'; then
    echo "Staged diff contains a real-looking ProduceID (3234 + 11 digits):"
    git diff --cached -U0 | grep -nE '3234[0-9]{11}'; status=1
fi
[ $status -eq 0 ] && echo "check_staged: OK (no media files, no real-looking IDs)"
exit $status
