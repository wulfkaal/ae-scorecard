# Public export validation

Validated 2026-11-16 with standard-library tools and no network requests.

- `python3 -m unittest discover -s tests`: 47 tests passed.
- The same suite passed with socket connection functions blocked.
- `python3 -m py_compile scripts/*.py` passed for both scripts.
- Python 3.9 syntax parsing passed for all Python files. Execution used the installed Python, not a Python 3.9 interpreter.
- Synthetic fixtures exercise cohort building, protection, comparison defaults, claims, sealed runs, retrieval, transport failures and trends, including an empty results directory and the monthly runner.
- Release scans found no restricted terms, private scholar names or identifiers, email addresses, long dashes, private paths or credential formats. Public owner identifiers, redacted placeholders and explicitly synthetic test values are allowed.
- All 23 retained site files match the original publication bytes. Two files referencing private internals were removed: `site/ae_scorecard.py` and `site/integration.md`.

Run the suite from the repository root. Collection commands are not part of release validation and may contact configured public services when run separately.

The root citation metadata uses CFF 1.2.0 fields; no external schema validator or dependencies were used. No DOI or distribution license is assigned.

Known limitations: preserved site pages and protocol retain references to the two omitted publication files and the historical standalone workflow. Use the repository script and README instructions. The distribution license remains the owner's decision. This directory is prepared for a public repository; it has not been uploaded.

`MANIFEST.txt` lists release file sizes and SHA-256 digests, excluding itself and generated caches or results.
