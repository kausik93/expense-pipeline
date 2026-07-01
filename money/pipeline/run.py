"""End-to-end: inbox of statements -> one month's categorized, reconciled CSV.

    python money/pipeline/run.py --month 4 --year 2026
    python money/pipeline/run.py --month 4 --year 2026 --inbox money/sample_data

Produces, in the output dir:
  <Mon><Year>.csv          ready to paste into the Google Sheet (transactions,
                           then the Category/Breakdown block and the two totals)
  <Mon><Year>_unknowns.csv any merchants that need the interactive step

UNKNOWN rows are written through (so reconciliation still holds) and listed
separately; they are never auto-written into merchants.yaml.
"""
from __future__ import annotations

import argparse
import calendar
import csv
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from money.pipeline import breakdown as bd  # noqa: E402
from money.pipeline import preflight  # noqa: E402
from money.pipeline.categorize import UNKNOWN, categorize, unknown_merchants  # noqa: E402
from money.pipeline.config import (  # noqa: E402
    load_categories, load_expected_accounts, load_sheets_config)
from money.pipeline.normalize import ingest  # noqa: E402

TXN_HEADER = ["Date", "Description", "Amount", "Account", "Category", "Notes"]


def _prev_month(today: date):
    return (12, today.year - 1) if today.month == 1 else (today.month - 1, today.year)


def _fmt(v: float) -> str:
    v = round(v, 2)
    return f"{v:.2f}" if v != 0 else "0.00"


def write_output_csv(path: Path, txns, breakdown: bd.Breakdown) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(TXN_HEADER)
        for _, r in txns.iterrows():
            w.writerow([r["Date"].strftime("%Y-%m-%d"), r["Description"],
                        _fmt(r["Amount"]), r["Account"], r["Category"], ""])
        w.writerow([])
        w.writerow(["", "Category", "Sum"])
        for cat, amt in breakdown.rows:
            w.writerow(["", cat, _fmt(amt)])
        w.writerow(["", "Overall total of sub-categories", _fmt(breakdown.total_subcategories)])
        w.writerow(["", "Sum of individual transactions", _fmt(breakdown.total_transactions)])


def write_unknowns_csv(path: Path, unknowns) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["merchant_key", "count", "total_amount", "example_description", "accounts"])
        for u in unknowns:
            w.writerow([u.key, u.count, _fmt(u.total_amount), u.example, "; ".join(u.accounts)])


def main(argv=None) -> int:
    today = date.today()
    dm, dy = _prev_month(today)
    p = argparse.ArgumentParser(description="Build one month's categorized expense CSV.")
    p.add_argument("--month", type=int, default=dm)
    p.add_argument("--year", type=int, default=dy)
    p.add_argument("--inbox", default=str(ROOT / "money" / "inbox"))
    p.add_argument("--out", default=str(ROOT / "money" / "output"))
    p.add_argument("--upload", action="store_true",
                   help="upload the month as a new tab in the configured Google Sheet")
    p.add_argument("--replace", action="store_true",
                   help="with --upload: replace the tab if it already exists")
    p.add_argument("--spreadsheet-id", default=None, help="override sheets.yaml")
    p.add_argument("--template-tab", default=None, help="override sheets.yaml")
    p.add_argument("--tab", default=None,
                   help="with --upload: override the new tab name (defaults to <Mon><Year>, e.g. Apr2026)")
    args = p.parse_args(argv)

    tag = f"{calendar.month_abbr[args.month]}{args.year}"
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    def rel(p: Path) -> str:
        try:
            return str(p.relative_to(ROOT))
        except ValueError:
            return str(p)

    # Prefer a per-month subfolder (money/inbox/Apr2026/); fall back to the base
    # folder if no subfolder exists, so a flat folder still works.
    base_inbox = Path(args.inbox)
    month_inbox = base_inbox / tag
    inbox = month_inbox if month_inbox.is_dir() else base_inbox

    ing = ingest(inbox, args.month, args.year)
    txns = ing.transactions

    print(f"=== {tag} ===")
    print(f"inbox: {rel(inbox.resolve())}")
    for fr in ing.files:
        print(f"  {fr.account:<26} {fr.format_name:<32} {fr.rows_in_month:>3} rows")
    if ing.unknown_formats:
        print("  ! UNKNOWN FORMATS (need a parser):")
        for name, header in ing.unknown_formats:
            print(f"    - {name}: {header}")
    if ing.unresolved_accounts:
        print("  ! UNRESOLVED ACCOUNTS (add to accounts.yaml):")
        for name in ing.unresolved_accounts:
            print(f"    - {name}")

    present_accounts = {fr.account for fr in ing.files}
    missing = preflight.missing_accounts(
        load_expected_accounts(), present_accounts, args.month, args.year)
    if missing:
        print("  ! MISSING EXPECTED ACCOUNTS (open card, no statement in inbox):")
        for name in missing:
            print(f"    - {name}")

    if txns.empty:
        print("No transactions for this month. Nothing written.")
        return 0

    categorized = categorize(txns)
    breakdown = bd.compute(categorized, load_categories())  # raises on reconciliation failure
    unknowns = unknown_merchants(categorized)

    n = len(categorized)
    n_unknown = int((categorized["Category"] == UNKNOWN).sum())
    coverage = 100 * (n - n_unknown) / n

    out_csv = out_dir / f"{tag}.csv"
    write_output_csv(out_csv, categorized, breakdown)

    print(f"\ntransactions:  {n}")
    print(f"auto-categorized: {n - n_unknown}/{n}  ({coverage:.1f}%)")
    print(f"reconciliation: OK  (sub-total == txn-total == {_fmt(breakdown.total_transactions)})")
    print(f"wrote {rel(out_csv)}")

    if unknowns:
        unk_csv = out_dir / f"{tag}_unknowns.csv"
        write_unknowns_csv(unk_csv, unknowns)
        print(f"\n{len(unknowns)} unknown merchant(s) -> {rel(unk_csv)} (need interactive categorization)")
        for u in unknowns:
            print(f"  {u.key!r}  x{u.count}  {_fmt(u.total_amount)}  e.g. {u.example!r}")

    if args.upload:
        # Import lazily so the run does not require google libs unless uploading.
        from money.pipeline import sheets  # noqa: E402
        cfg = load_sheets_config()
        sid = args.spreadsheet_id or cfg["spreadsheet_id"]
        template = args.template_tab or cfg["template_tab"]
        new_tab = args.tab or tag
        if unknowns:
            print(f"\nNote: uploading with {len(unknowns)} UNKNOWN row(s) still present.")
        try:
            url = sheets.upload(sid, template, new_tab, categorized, load_categories(),
                                replace=args.replace)
            print(f"\nuploaded {new_tab!r} -> {url}")
        except sheets.SheetsError as e:
            print(f"\nupload failed: {e}")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
