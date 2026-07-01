# expense-pipeline

Turn a month of downloaded bank/card statement CSVs into **one categorized,
reconciled monthly output** — a paste-ready CSV, or a formatted tab pushed
straight into a Google Sheet.

Different banks export wildly different CSV shapes (Chase credit vs. Chase bank,
Capital One's split debit/credit columns, Citi's sign conventions, Venmo's
banner rows). This pipeline parses each one, resolves which account it is,
collapses merchant noise into stable keys, categorizes every transaction, and
refuses to finish unless the per-category totals reconcile to the penny against
the raw transaction total.

## Design: deterministic core, LLM only at the fuzzy edges

The guiding principle is that **anything that can be deterministic is plain
Python**; the LLM is reserved for the two cases that genuinely need judgment:

- a **never-seen merchant** → the agent proposes a category, you confirm, and
  the choice is written into `merchants.yaml` so it's deterministic next time.
- a **never-seen file format** → the run refuses to guess, surfaces the exact
  header, and the agent helps author a new parser.

Parsing, account resolution, categorization, and the per-category math are all
reproducible code with no model in the loop. Format detection is content-based
(header fingerprint), and account identity is filename-based — kept separate so
the two common drift cases (new card / new export format) degrade gracefully
instead of silently corrupting a month.

A hard **reconciliation guard** is the backbone: if the sum of the category
breakdown ever diverges from the sum of individual transactions, the run aborts.
A clean run is, by construction, a reconciled run.

## The `expenses` Claude Code skill

Day to day this is driven by a Claude Code skill (`.claude/skills/expenses/`):
you drop statements into a per-month folder and say "process my April expenses."
The skill is deliberately thin — it just runs the deterministic pipeline and
orchestrates the two human-judgment follow-ups above (unknown merchant, unknown
format), always teaching the config rather than hand-editing output, so the next
run needs less of it. See [`.claude/skills/expenses/SKILL.md`](.claude/skills/expenses/SKILL.md).

## Quick start

```bash
pip install -r money/requirements.txt

# Run the included synthetic sample month end-to-end:
python money/pipeline/run.py --month 4 --year 2026 --inbox money/sample_data --out /tmp/out
```

For your own data, drop statement CSVs into `money/inbox/<MonYYYY>/` (e.g.
`money/inbox/Apr2026/`) and run `python money/pipeline/run.py --month 4 --year 2026`.
Real statements and generated output are gitignored.

Output: `<Mon><Year>.csv` (transactions, the per-category Sum block, and the two
reconciling totals) plus `<Mon><Year>_unknowns.csv` (merchants still needing a
category).

### Optional: upload to a Google Sheet

Pass `--upload` to duplicate a formatted template tab and write the month into
the copy (formatting and `=SUMIF` formulas are inherited, not recreated).
Configure your target in `money/config/sheets.yaml` (or pass `--spreadsheet-id`
/ `--template-tab`). Auth is installed-app OAuth; the pipeline reads your
`client_secret.json` from `$GOOGLE_OAUTH_CLIENT_SECRETS` or `~/.config/expenses/`
and caches the refresh token locally. No credentials are committed.

## Layout

```
money/
  pipeline/
    parsers/      one parser per source format, chosen by header fingerprint
    text.py       merchant_key(): description -> stable merchant key
    normalize.py  parse files, resolve accounts, month-filter, combine
    categorize.py match merchant key against merchants.yaml (else UNKNOWN)
    breakdown.py  per-category sums + hard reconciliation guard
    sheets.py     optional Google Sheets upload
    run.py        entrypoint
  config/
    categories.yaml  canonical category list (the only allowed labels)
    accounts.yaml    statement filename -> friendly account name
    merchants.yaml   merchant key -> category (the curated "brain")
    sheets.yaml      Google Sheets upload target (placeholder values)
    expected_accounts.yaml  pre-flight completeness registry
  sample_data/    synthetic fixtures (one CSV per source format)
  tests/          parser smoke checks + sheets-payload layout checks
.claude/skills/expenses/   the Claude Code skill that drives the pipeline
```

See [`money/README.md`](money/README.md) for the detailed workflow, drift
handling, and categorizer notes.

## Tests

```bash
python money/tests/test_parsers.py          # every parser vs. the sample fixtures
python money/tests/test_sheets_payload.py   # SUMIF/SUM formula ranges & layout
```

## Notes

The config files (`accounts.yaml`, `expected_accounts.yaml`, `merchants.yaml`,
`sheets.yaml`) ship with **generic example values** that line up with the
synthetic sample data. Replace them with your own accounts and categories.
`merchants.yaml` is normally bootstrapped from years of your own hand-categorized
history via `bootstrap_merchants.py`; the committed starter list is a small set
of well-known national merchants so the demo categorizes out of the box.
