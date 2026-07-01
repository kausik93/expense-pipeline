"""Format detection + dispatch.

`parse_file` fingerprints a CSV by its header and routes it to the matching
parser. A file whose fingerprint matches nothing raises `UnknownFormatError`
carrying the header — that's the signal for the skill to ask a human to author
a new parser, rather than silently mis-parsing.
"""
from __future__ import annotations

import csv
from typing import List, Optional, Tuple

import pandas as pd

from . import capital_one, chase, citi, venmo
from .base import Parser

# Order matters only for custom detectors; header-equality matches are exclusive.
# Venmo first because its detector keys off the banner row.
ALL_PARSERS: List[Parser] = [venmo.PARSER, *chase.PARSERS, capital_one.PARSER, citi.PARSER]


class UnknownFormatError(Exception):
    def __init__(self, path: str, header: List[str]):
        self.path = path
        self.header = header
        super().__init__(
            f"unrecognized export format for {path!r}; header was: {header}"
        )


def _read_first_row(path: str) -> Tuple[List[str], str]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        raw = f.readline()
        f.seek(0)
        fields = next(csv.reader([raw])) if raw else []
    return [c.strip() for c in fields], raw


def detect(path: str) -> Optional[Parser]:
    fields, raw = _read_first_row(path)
    for parser in ALL_PARSERS:
        if parser.matches(fields, raw):
            return parser
    return None


def parse_file(path: str) -> Tuple[pd.DataFrame, str]:
    parser = detect(path)
    if parser is None:
        fields, _ = _read_first_row(path)
        raise UnknownFormatError(path, fields)
    return parser.parse_fn(path), parser.name
