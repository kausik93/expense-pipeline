# money

Expense pipeline: a month of downloaded bank/card statement CSVs → one
categorized, reconciled CSV to paste into the expenses Google Sheet.

The design principle is a **deterministic core with the LLM only at the edges**.
Parsing, account resolution, categorization, and the per-category math are plain
Python and fully reproducible. The LLM (via the `expenses` skill) is pulled in
only for the two irreducibly fuzzy cases: a never-seen merchant and a never-seen
file format. Both get codified into config on resolution, so they are
deterministic on the next run.

## Usage

Day to day, drive this through the **`expenses` skill** — just ask Claude (e.g.
"process my April expenses"). You only:

1. Download your statements and drop them into a per-month folder
   `money/inbox/<MonYYYY>/` (e.g. `money/inbox/Apr2026/`, no spaces).
2. Ask the skill. It runs the pipeline and walks you through any unknown
   merchants (proposes categories, you pick, the choice is saved).

Under the hood — and as a manual escape hatch (e.g. on Termux) — the skill just
runs:

```
python money/pipeline/run.py --month 4 --year 2026
```

Output (`money/output/`, gitignored): `Apr2026.csv` (paste-ready: transactions,
the per-category Sum block, and the two reconciling totals) and
`Apr2026_unknowns.csv` (merchants still needing categorization).

### Uploading to the live Google Sheet

Pass `--upload` to push the month directly into the configured Google Sheet
(`config/sheets.yaml`) instead of (or in addition to) the CSV:

```
python money/pipeline/run.py --month 4 --year 2026 --upload          # new tab
python money/pipeline/run.py --month 4 --year 2026 --upload --replace # overwrite
```

Each upload **duplicates the template tab** (`Nov2025` by default) and writes
into the copy — so Arial / bold headers / column widths / `=SUMIF` formulas are
inherited from the template rather than recreated. Errors loudly if the target
tab already exists (no silent clobbering); `--replace` deletes-and-redoes.

One-time auth setup:
1. Put your Google OAuth client_secret JSON anywhere the loader can find it —
   easiest is `~/.config/expenses/client_secret.json`. (Auto-detected from
   `~/Downloads/client_secret_*.json` as a convenience.)
2. Enable the **Google Sheets API** for the GCP project that issued that
   client_secret.
3. First `--upload` opens a browser to consent; the refresh token is cached at
   `~/.config/expenses/token.json` so later runs are non-interactive.

## Layout

```
pipeline/
  parsers/        one parser per source format, chosen by header fingerprint
  text.py         merchant_key(): description -> stable merchant key
  normalize.py    parse all files, resolve accounts, month-filter, combine
  categorize.py   match merchant key against merchants.yaml (else UNKNOWN)
  breakdown.py    per-category sums + hard reconciliation guard
  run.py          entrypoint
  bootstrap_merchants.py   build merchants.yaml from the historical workbook
config/
  categories.yaml the canonical category list (the only allowed labels)
  accounts.yaml   statement filename -> friendly account name
  merchants.yaml  merchant key -> category (curated "brain", committed)
sample_data/      synthetic fixtures (one CSV per source format) for the demo + tests
tests/            parser smoke checks + held-out categorization validation
```

## How drift is handled

Format and account identity are decided independently, so the two common drift
cases degrade gracefully instead of silently corrupting output:

- **New card, known format** → parses automatically; only needs an
  `accounts.yaml` line for its display name (flagged as an unresolved account).
- **Known card, new format** → raises `UnknownFormatError` with the header
  (flagged as an unknown format); needs a new parser, never mis-parsed.

## Categorizer

`merchants.yaml` is bootstrapped once from years of hand-categorized history
(majority vote per merchant key), then grown by the interactive step whenever a
new merchant appears. On a held-out month it reproduces ~86% of hand labels
where a rule exists; the remainder are merchants categorized inconsistently in
the past (Amazon, Costco, etc.) and are surfaced for a human decision.
