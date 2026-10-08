# Plan: build `kling-label`

Spec: [../specs/2026-10-08-kling-label-cli-design.md](../specs/2026-10-08-kling-label-cli-design.md)

Each step is TDD: write the failing tests, run them and see them fail, write
the code, run all tests, then commit after the staged-diff scan
(`scripts/check_staged.sh`). Nothing is pushed without the owner's OK.

1. **Skeleton.** `pyproject.toml`, `src/kling_label/__init__.py`,
   `tests/__init__.py` (adds `src` to the path), `scripts/check_staged.sh`.
2. **Fakes.** `tests/fakes.py`: `png_bytes(...)`, `mp4_bytes(...)`,
   `jpeg_bytes(...)`, `aigc_json(...)` with made-up IDs only.
3. **`produce_id.py`.** Tests: made-up ID decodes to `2026-01-10 07:01:59 UTC`;
   `ai_app` client; wrong shapes return `None`.
4. **`producer.py`.** Tests: `kling`; valid USCC form; wrong check digit;
   unknown string.
5. **`label.py`.** Tests: payload checks, "is Kling?" rules, result kinds.
6. **`png.py`.** Tests from spec section 7 (PNG list).
7. **`mp4.py`.** Tests from spec section 7 (MP4 list).
8. **`scan.py`.** Raw scan and XMP field reader; block-boundary test.
9. **`sniff.py` + `detect.py`.** The find order; tests per file type.
10. **`cli.py` + `__main__.py`.** Text and JSON output, several files, exit
    codes.
11. **README.** Install and usage; update roadmap. Update CLAUDE.md status.
12. **Final check.** Full test run, `pip install .` in a temp venv and run
    `kling-label` on generated fakes; scan the full diff; ask before pushing.
