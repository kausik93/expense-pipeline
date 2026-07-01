---
name: expenses
description: >
  Turn a month of downloaded bank/card statement CSVs into one categorized,
  reconciled CSV ready to paste into the expenses Google Sheet. Use when the
  user wants to process expenses, categorize transactions, close out a month,
  or mentions dropping bank statements / Chase / Capital One / Citi / Venmo CSVs
  into the money pillar.
---

# Expenses

Thin orchestration over the deterministic pipeline in `money/pipeline/`. The
Python does all parsing, categorization, and math; you only step in for the two
things that genuinely need judgment: an **unknown merchant** and an **unknown
file format**. Never categorize by hand-editing the output — always teach the
config so the next run is deterministic.

## Run a month

1. Confirm the user has dropped their statement CSVs into a per-month subfolder
   `money/inbox/<MonYYYY>/` (e.g. `money/inbox/Apr2026/`, no spaces; real
   statements are gitignored). Ask which month/year to process if unclear. The
   run also accepts a flat `money/inbox/` if no subfolder exists.
2. Run:

   ```
   python money/pipeline/run.py --month <M> --year <Y>
   ```

3. Read the summary. It reports per-account row counts, auto-categorization
   coverage, the reconciliation result, and three kinds of follow-up. Resolve
   them in this order, re-running after each, until coverage is 100% and there
   are no warnings.

4. Once the month is clean, upload to the Google Sheet by re-running with
   `--upload` (add `--replace` if the tab already exists). The upload duplicates
   the template tab (see `money/config/sheets.yaml`) so formatting/formulas
   carry over automatically. First time only, this opens a browser for OAuth
   consent; subsequent runs are silent.

The final `money/output/<Mon><Year>.csv` is laid out exactly like a monthly tab
(transactions, then the `Category`/`Breakdown` block, then the two totals). The
run refuses to finish if the breakdown total ever diverges from the transaction
total, so a clean run is a reconciled run.

## Follow-up 1: unknown merchants (the common case)

Listed in the summary and in `money/output/<Mon><Year>_unknowns.csv` as
`merchant_key, count, total_amount, example_description, accounts`.

For each unknown, do the interactive step:
- Propose a few ranked candidate categories (from `money/config/categories.yaml`
  only) with a one-line reason each, based on the merchant name. Let the user
  pick one or supply their own.
- Append the confirmed choice to `money/config/merchants.yaml` under `rules:`,
  keyed by the **`merchant_key`** from the unknowns file (not the raw
  description), e.g. `  MENTORCRUISE.COM SAMMAMISH WA: Productivity Tooling`.
- Never write a guess the user hasn't confirmed.

Then re-run; those rows now categorize deterministically and reconciliation
absorbs them. Batch the questions when there are several.

## Follow-up 2: unresolved account

A statement whose filename matches no rule in `money/config/accounts.yaml`
parses fine but shows as `UNRESOLVED: <filename>`. Ask the user what account it
is, add a `match`/`name` line to `accounts.yaml`, and re-run.

## Follow-up 3: unknown file format

If a file's header matches no parser, the run lists it under "UNKNOWN FORMATS"
with the header. This is real format drift. To onboard it:
- Read a few rows of the file to understand the columns.
- Add a parser in `money/pipeline/parsers/` (see existing ones): declare the
  exact `header`, and a `parse_fn` that returns canonical `Date/Description/Amount`
  with the sign convention "spend negative, money-in positive". Register it in
  `parsers/__init__.py::ALL_PARSERS`.
- Run `python money/tests/test_parsers.py` and re-run the month.

## Re-bootstrapping the categorizer

`merchants.yaml` is generated once from history and then hand-grown by the
interactive step above. Only re-run the bootstrap if the historical workbook
itself materially changes:

```
python money/pipeline/bootstrap_merchants.py [path/to/workbook.xlsx]
```

It reports ambiguous merchants (categorized inconsistently in the past) in
`money/config/merchants_review.txt` — worth a glance, since those are where the
categorizer is least confident.
