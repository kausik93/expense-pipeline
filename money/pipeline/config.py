"""Loaders for the committed YAML config (the curated 'brain')."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import yaml

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


def _load(name: str):
    with open(CONFIG_DIR / name, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_categories() -> List[str]:
    return _load("categories.yaml")


def load_account_rules() -> List[Dict[str, str]]:
    return _load("accounts.yaml")["accounts"]


def load_merchants() -> Dict[str, str]:
    """Return {pattern: category}. Empty if not yet bootstrapped."""
    path = CONFIG_DIR / "merchants.yaml"
    if not path.exists():
        return {}
    data = _load("merchants.yaml") or {}
    return data.get("rules", {})


def load_sheets_config() -> Dict[str, str]:
    """Return {'spreadsheet_id': ..., 'template_tab': ...} for the upload target."""
    return _load("sheets.yaml")


def load_expected_accounts() -> List[Dict[str, str]]:
    """Return the expected-accounts registry (for the pre-flight check).

    Empty if the file is absent, so the check simply no-ops until it exists.
    """
    path = CONFIG_DIR / "expected_accounts.yaml"
    if not path.exists():
        return []
    return (_load("expected_accounts.yaml") or {}).get("accounts", [])
