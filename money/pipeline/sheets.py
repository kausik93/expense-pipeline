"""Upload a categorized month to the live Google Sheet.

Strategy: duplicate a known-good template tab (e.g. Nov2025) and then write
values into the copy. Duplicating inherits all formatting (Arial, bold headers,
column widths, etc.), so we never have to replicate formatting cell-by-cell —
we just put values and formulas into the right cells.

The breakdown is written as `=SUMIF` / `=SUM` formulas (matching the template),
so the totals stay live as the user re-categorizes inside the sheet later.

Auth uses installed-app OAuth. The first run opens a browser once; the refresh
token is cached at ~/.config/expenses/token.json. The OAuth client_secret is
read from $GOOGLE_OAUTH_CLIENT_SECRETS, else ~/.config/expenses/client_secret.json,
else the first matching client_secret_*.json in ~/Downloads.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import pandas as pd
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
CONFIG_HOME = Path(os.path.expanduser("~/.config/expenses"))
TOKEN_PATH = CONFIG_HOME / "token.json"

TXN_COLS = ["Date", "Description", "Amount", "Account", "Category", "Notes"]


class SheetsError(Exception):
    pass


# ---------- auth ----------

def _find_client_secret() -> Path:
    env = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRETS")
    if env:
        return Path(env).expanduser()
    local = CONFIG_HOME / "client_secret.json"
    if local.exists():
        return local
    downloads = sorted(Path.home().glob("Downloads/client_secret_*.json"))
    if downloads:
        return downloads[0]
    raise SheetsError(
        "no OAuth client_secret found. Set $GOOGLE_OAUTH_CLIENT_SECRETS, or place "
        f"the JSON at {local}, or download client_secret_*.json into ~/Downloads."
    )


def get_credentials() -> Credentials:
    CONFIG_HOME.mkdir(parents=True, exist_ok=True)
    creds: Optional[Credentials] = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            secret = _find_client_secret()
            flow = InstalledAppFlow.from_client_secrets_file(str(secret), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_PATH.write_text(creds.to_json())
    return creds


def get_service():
    return build("sheets", "v4", credentials=get_credentials(), cache_discovery=False)


# ---------- helpers ----------

@dataclass
class TabInfo:
    sheet_id: int
    title: str


def _tab_index(svc, spreadsheet_id: str) -> dict:
    meta = svc.spreadsheets().get(spreadsheetId=spreadsheet_id, fields="sheets(properties)").execute()
    return {s["properties"]["title"]: TabInfo(s["properties"]["sheetId"], s["properties"]["title"])
            for s in meta["sheets"]}


def _fmt_amount(v: float) -> float:
    return round(float(v), 2)


def _build_payload(categorized: pd.DataFrame, categories: List[str], extras: List[str]):
    """Return (txn_rows, breakdown_block) where:
       - txn_rows is the value matrix for A1:F{N+1}
       - breakdown_block is the value matrix to put starting at B{N+3}
    """
    header = TXN_COLS
    txn_rows: List[List] = [header]
    for _, r in categorized.iterrows():
        txn_rows.append([
            r["Date"].strftime("%Y-%m-%d"),
            r["Description"],
            _fmt_amount(r["Amount"]),
            r["Account"],
            r["Category"],
            "",
        ])
    n_txn = len(categorized)
    txn_last_row = n_txn + 1  # header at 1, data 2..n+1

    block_start_row = txn_last_row + 2  # blank row, then header
    # rows: header (Category|Sum), then each category, then blank, then two totals
    block = [["Category", "Sum"]]
    bd_cat_rows = []  # row numbers of category lines for SUM range
    cur = block_start_row + 1  # first category row
    for cat in categories + extras:
        formula = f'=SUMIF(E2:E{txn_last_row}, B{cur}, C2:C{txn_last_row})'
        block.append([cat, formula])
        bd_cat_rows.append(cur)
        cur += 1
    first_cat, last_cat = bd_cat_rows[0], bd_cat_rows[-1]
    # Nov 2025 puts the totals immediately after the last category — no blank row.
    block.append(["Overall total of sub-categories", f'=SUM(C{first_cat}:C{last_cat})'])
    block.append(["Sum of individual transactions", f'=SUM(C2:C{txn_last_row})'])
    return txn_rows, block, block_start_row, txn_last_row


# ---------- main upload ----------

def upload(spreadsheet_id: str, template_tab: str, new_tab: str,
           categorized: pd.DataFrame, categories: List[str],
           replace: bool = False, svc=None) -> str:
    svc = svc or get_service()
    tabs = _tab_index(svc, spreadsheet_id)
    if template_tab not in tabs:
        raise SheetsError(f"template tab {template_tab!r} not found in spreadsheet")
    if new_tab in tabs:
        if not replace:
            raise SheetsError(
                f"tab {new_tab!r} already exists. Pass --replace to overwrite, "
                f"or rename the existing tab.")
        # delete the existing tab so the duplicate can take its name
        svc.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [{"deleteSheet": {"sheetId": tabs[new_tab].sheet_id}}]},
        ).execute()

    # 1. Duplicate the template tab (inherits its formatting). We let Sheets
    # place it adjacent to the source rather than guessing where the user wants
    # it among their many tabs — easy to drag once.
    resp = svc.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": [{
            "duplicateSheet": {
                "sourceSheetId": tabs[template_tab].sheet_id,
                "newSheetName": new_tab,
            }
        }]},
    ).execute()
    new_sheet_id = resp["replies"][0]["duplicateSheet"]["properties"]["sheetId"]

    # 2. Clear values in the duplicate (formatting stays). Clear a generous block.
    svc.spreadsheets().values().clear(
        spreadsheetId=spreadsheet_id,
        range=f"'{new_tab}'!A1:Z1000",
    ).execute()

    # 3. Compute extras (categories present in df but not in categories.yaml)
    canon_set = set(categories)
    extras = sorted(c for c in categorized["Category"].unique() if c not in canon_set)

    txn_rows, block, block_start, txn_last = _build_payload(categorized, categories, extras)

    # 4. Write transactions A1:F{N+1} and the breakdown block at B{block_start}
    svc.spreadsheets().values().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
            "valueInputOption": "USER_ENTERED",
            "data": [
                {"range": f"'{new_tab}'!A1", "values": txn_rows},
                {"range": f"'{new_tab}'!B{block_start}", "values": block},
            ],
        },
    ).execute()

    return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit#gid={new_sheet_id}"
