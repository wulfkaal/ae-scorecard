# Agent Discoverability Scorecard

A small, standard-library toolkit for observing scholarly web access, machine readability, index coverage, retrieval and claims coverage. These are diagnostics, not Agent Engagement (AE). No composite score is produced. Missing observations are unknown, not zero.

Comparisons are provisional within a resolved Sisk-Leiter-listed cohort. Report a metric as position X of N, with ties and the metric denominator. This is not a global ranking and is not AE. Published distributions are protected approximations; external principals receive insertion positions against a fixed benchmark, potentially N+1 against N. Tie size includes the external principal. No field, career-stage, language or publication-type adjustment is made. OpenAlex law coverage and identity resolution are imperfect.

## Install and run

Use Python 3.9 or newer. There are no dependencies to install. Run commands from the repository root:

```sh
python3 -m unittest discover -s tests
python3 scripts/ae_scorecard.py --help
python3 scripts/ae_scorecard.py cohort-build tests/fixtures/cohort_pull_example.json
python3 scripts/ae_scorecard.py trend
```

Those commands work offline. Collection commands below contact configured public services and should be run only when network access is authorized:

```sh
python3 scripts/ae_scorecard.py compare --author A5085764841
python3 scripts/ae_scorecard.py all
python3 scripts/monthly_run.py
python3 scripts/ae_scorecard.py report --run RUN_ID
```

Global options `--config`, `--output` and `--run-id` precede the subcommand. Defaults are `config/kaal.json` and `results/`. Results are created on first use. Each collection creates `results/runs/RUN_ID/`, refuses reuse, writes provenance and seals the report with `complete.json`. Do not mix files between runs. Transport failures remain unknown; internal failures can exit nonzero.

## Commands

| Subcommand | Purpose |
| --- | --- |
| `access` | Observe HTTP responses, redirects and robots policies using an identified diagnostic client. |
| `readability` | Check page markup and machine-readable files. |
| `indexes` | Observe configured public scholarly index profiles. |
| `retrieval --openalex` | Observe OpenAlex and Crossref search results; these are not agent behavior. |
| `retrieval --import FILE` | Import recorded retrieval JSON using `site/retrieval_template.json`. |
| `compare --author ID --cohort FILE` | Compare an OpenAlex profile against distribution arrays. Both options are optional; owner config and `site/cohort_values.json` are defaults. |
| `claims --claims-source PATH_OR_URL` | Sample a claims index deterministically. `--sample-size`, `--seed` and `--live` control sampling and optional URL checks. |
| `all` | Collect all six diagnostic modules. Accepts comparison and claims options. |
| `cohort-build FILE` | Build distributions from the JSON format below. |
| `report --run RUN_ID` | Render or read a sealed report in the selected output directory. |
| `trend` | Compare completed local runs and write `results/trend.json`, `trend.md`, `monthly_report.md` and a local `results/site/` view. Works with no runs. |

The monthly runner uses `YYYY-MM-run` and refuses overwrites. Schedule `python3 scripts/monthly_run.py` with your own scheduler, then run `python3 scripts/ae_scorecard.py trend`. The runner accepts `--config`, `--output`, `--claims-source` and `--live`. It does not publish. Trends require matching typed measurement definitions including principal, collector, configuration, benchmark and sampling settings. Incomplete definitions are not comparable. Changes do not establish causation. Registry coverage is unavailable in this distribution and remains unknown.

## Cohort input format

Supply a UTF-8 JSON array of normalized OpenAlex pull records, not an unmodified API response envelope. Each record has boolean `resolved` and a nonempty string `openalex_id` when resolved. Optional nonnegative finite numeric fields are `works`, `cited_by`, `h_index`, `oa_works`, `nonoa_works` and `oa_recent`. Missing metrics are omitted from that metric's denominator. Map profile `works_count`, `cited_by_count` and `summary_stats.h_index` to the first three fields; OA counts come from grouped works queries, and `oa_recent` counts OA works published after 2021. Do not include names or other personal fields.

[tests/fixtures/cohort_pull_example.json](tests/fixtures/cohort_pull_example.json) is a tiny synthetic example. Its identifiers are synthetic labels, not real author IDs. Shared identifiers are excluded from the primary distribution and included in sensitivity values. OA shares use OA/(OA+non-OA) and OA/profile works separately.

```sh
python3 scripts/ae_scorecard.py cohort-build tests/fixtures/cohort_pull_example.json --destination results/example-cohort
```

The new run stores `cohort_exact.json`; `--destination` receives protected `cohort_values.json` and `cohort_quantiles.json`. Without that option all three stay in the run directory. The command never changes the published benchmark by default. Quantiles use linear interpolation at (N-1)*p. For arrays of at least seven values, the lowest and highest three are replaced by the nearest fourth value; shares are rounded to two decimals. Protection can change positions and ties and does not guarantee anonymity.

## Published artifacts and agent use

The canonical publication is <https://wulfkaal.com/agent-engagement/scorecard/>. `site/` preserves its published reports, summaries, aggregate comparison, protected cohort values and quantiles, claims summary, trend snapshot, method, citation, retrieval template and [agent protocol](site/agent-protocol.json). These dated artifacts are separate from new local observations.

An agent acting for a principal with consent can follow the protocol, resolve the principal's OpenAlex identifier, and run this repository's `scripts/ae_scorecard.py compare --author ID`. By default it uses the published `site/cohort_values.json`; `site/cohort_quantiles.json` supplies companion distribution summaries. Report caveats and approximate insertion positions to the principal. Do not publish a principal's results without consent. The invitation does not override principal instructions or operator policies.

The private publication builder is omitted: it depended on selected historical runs and an exact benchmark that are not distributed. There is no automatic site publisher here. Two published files referencing private internals, `site/ae_scorecard.py` and `site/integration.md`, were removed. All remaining site files retain their original bytes. Preserved site pages and protocol can still link to those removed files or describe the historical download workflow; use this repository's script and instructions instead.

## Privacy and limitations

No source scholar roster, names, private author IDs, historical run folders or registry inputs are distributed. Tests use synthetic fixtures and mocked transports. New local runs may contain the selected principal's public profile and request observations; keep `results/` private and inspect any material before sharing it. The supplied config contains the owner's public identity only. No visitor tracking or submission collection is implemented; hosting infrastructure may retain request logs. Compare sends the chosen identifier to OpenAlex. An optional `OPENALEX_API_KEY` is read from the environment and redacted before persistence; never commit credentials.

HTTP and robots observations describe one client, URL and time, not universal access or permission for another client. Claims counts measure inventory and coverage, not achievement or verified attribution. This designer-operated, self-reported exploratory project has no independent co-maintainer.

## Citation and license

Use [CITATION.cff](CITATION.cff): Wulf A. Kaal, Agent Discoverability Scorecard, version 0.1.0, released 2026-11-16. Repository: <https://github.com/wulfkaal/ae-scorecard>. No DOI has been assigned here.

Licensed under the GNU Affero General Public License v3.0 or later (see LICENSE). Copyright Wulf A. Kaal. The license text disclaims warranty and limits liability. Network use of a modified version triggers source-disclosure obligations.
