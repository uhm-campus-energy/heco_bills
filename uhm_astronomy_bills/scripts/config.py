"""
config.py — everything specific to the ASTRONOMY bill pipeline.

PATHS ARE PORTABLE:
This finds the "heco_bills" root automatically, based on where THIS file
sits, so the same code works on your laptop and later on the server
without editing any paths.

Actual folder layout this expects:

    heco_bills/
    ├── heco_common.py
    └── uhm_astronomy_bills/
        ├── scripts/
        │   ├── config.py                       <- this file
        │   ├── 1) organize_astronomy_bills.py
        │   └── 3) upload_and_archive.py
        ├── input_bills/
        ├── bill_archive/
        └── output/
"""

import re
from pathlib import Path

# ── Find folders automatically, relative to this file ────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent      # .../heco_bills/uhm_astronomy_bills/scripts
PROJECT_DIR = SCRIPT_DIR.parent                    # .../heco_bills/uhm_astronomy_bills
HECO_BILLS_ROOT = SCRIPT_DIR.parent.parent         # .../heco_bills  (where heco_common.py lives)

# ── Paths ──────────────────────────────────────────────────────────────
SOURCE_DIR = PROJECT_DIR / "input_bills"
ARCHIVE_DIR = PROJECT_DIR / "bill_archive"
DUPLICATE_DIR = SOURCE_DIR / "duplicate_bills"
OUTPUT_CSV = PROJECT_DIR / "output" / "astronomy_bills_data.csv"

# ── Filename ──────────────────────────────────────────────────────────
# Canonical format: ACCOUNTNUMBER_YYYY_MM_DD_astronomy_bill.pdf
FILENAME_SUFFIX = "astronomy_bill"

FILENAME_PATTERN = re.compile(
    r"^(?P<acct>\d+)_(?P<year>\d{4})_(?P<month>\d{2})_(?P<day>\d{2}).*\.pdf$",
    re.IGNORECASE,
)

# ── Database (step 3) ────────────────────────────────────────────────
DATABASE = "uhm2023"
TABLE = "heco.kwh"
COLUMNS = ["contract", "date_end", "kwh", '"cost$"', "days"]

# ── Database (step 0) ─────────────────────────────────────────────────
# extracts/ is shared across all heco_bills projects, so it lives at the
# repo root next to heco_common.py, not inside uhm_astronomy_bills/.
EXTRACTS_DIR = HECO_BILLS_ROOT / "extracts"
LAST_DATES_QUERY = "SELECT contract, max FROM heco.dates_heco_direct_bills order by contract"
LAST_DATES_CSV = EXTRACTS_DIR / "dates_heco_direct_bills.csv"


# ── PDF parsing (project-specific — every bill layout is different) ───

import pdfplumber
from datetime import date


def extract_bill_info(pdf_path):
    """
    Extract (account_number, 'YYYY_MM_DD') from an astronomy bill PDF.
    This is the one function organize_bills() can't share across projects,
    because each bill's layout is different.
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = pdf.pages[0].extract_text()
            if not text:
                return None, None

            account_match = re.search(r"Account Number:.*\n(\d+)", text)
            account_number = account_match.group(1) if account_match else None

            service_period_match = re.search(
                r"Service Period\s+\d{2}/\d{2}/\d{2}\s*-\s*(\d{2})/(\d{2})/(\d{2})", text
            )
            if service_period_match:
                month, day, year_short = service_period_match.groups()
                date_str = f"20{year_short}_{month}_{day}"
            else:
                date_str = None

            return account_number, date_str
    except Exception as e:
        print(f"  [ERROR] Reading {pdf_path.name}: {e}")
        return None, None


def get_contract_and_date(pdf_path):
    """
    Extract (contract_number, bill_date) from an astronomy bill PDF, for
    checking against extracts/dates_heco_direct_bills.csv (script 0).

    The "Contract" number is a different value from the "Account Number"
    used in the canonical filename — e.g. Account Number 201018793350
    pairs with Contract 32616132 on the same bill. bill_date is the END
    of the Service Period (a datetime.date), matching what's stored in
    the database as date_end.
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = pdf.pages[0].extract_text()
            if not text:
                return None, None

            contract_match = re.search(
                r"Invoice Number:.*?Contract:\s*\n\s*\d+\s+(\d+)", text
            )
            contract = contract_match.group(1) if contract_match else None

            service_period_match = re.search(
                r"Service Period\s+\d{2}/\d{2}/\d{2}\s*-\s*(\d{2})/(\d{2})/(\d{2})", text
            )
            bill_date = None
            if service_period_match:
                month, day, year_short = service_period_match.groups()
                bill_date = date(2000 + int(year_short), int(month), int(day))

            return contract, bill_date
    except Exception as e:
        print(f"  [ERROR] Reading {pdf_path.name}: {e}")
        return None, None
