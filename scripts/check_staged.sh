#!/bin/sh
# Stops a commit (or a pull request) that contains image/video files or something that
# looks like a real Kling ProduceID: a 15-digit number starting 31..39. Real IDs began at
# 2886 in Sep 2025, were 3234 in Oct 2026 and grow about 86,400 per day, so a fixed prefix
# goes stale. Made-up IDs in this repo start with 30 (e.g. 3000000...), so they pass.
#
# Usage:
#   scripts/check_staged.sh                 check the staged changes (run before every commit)
#   scripts/check_staged.sh BASE..HEAD      check every commit in a range (used by CI); an ID
#                                           added and removed again in the range is still found
status=0
RANGE="$1"
if [ -n "$RANGE" ]; then
    names() { git log --name-only --format= --diff-filter=ACMR "$RANGE"; }
    patch() { git log -p -U0 --format= "$RANGE"; }
else
    names() { git diff --cached --name-only --diff-filter=ACMR; }
    patch() { git diff --cached -U0; }
fi
bad_files=$(names | sort -u | grep -iE '\.(png|jpe?g|webp|gif|heic|mp4|mov|m4v|avi|mkv)$')
if [ -n "$bad_files" ]; then
    echo "Media files (not allowed):"; echo "$bad_files"; status=1
fi
ID_RE='(^|[^0-9])3[1-9][0-9]{13}([^0-9]|$)'
if patch | grep -E '^\+' | grep -vE '^\+\+\+' | grep -qE "$ID_RE"; then
    echo "Real-looking ProduceID found (15 digits starting 31-39):"
    patch | grep -E '^\+' | grep -vE '^\+\+\+' | grep -nE "$ID_RE" | cut -c1-160; status=1
fi
[ $status -eq 0 ] && echo "check_staged: OK (no media files, no real-looking IDs)"
exit $status
