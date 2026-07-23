"""
config.py — everything specific to the SUBSTATION bill pipeline.

PATHS ARE PORTABLE:
This finds the "heco_bills" root automatically, based on where THIS file
sits, so the same code works on your laptop and later on the server
without editing any paths.

Actual folder layout this expects:

    heco_bills/
    ├── heco_common.py
    └── uhm_substation_bills/
        ├── scripts/
        │   ├── config.py                       <- this file
        │   ├── 1) organize_substation_bills.py
        │   ├── 2) substation_bill_extract.py
        │   ├── 3) upload_csv_to_database.py
        │   └── 4) move_to_archive.py
        ├── input_bills/
        ├── bill_archive/
        └── output/
"""

import re
from pathlib import Path

# ── Find folders automatically, relative to this file ────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent      # .../heco_bills/uhm_substation_bills/scripts
PROJECT_DIR = SCRIPT_DIR.parent                    # .../heco_bills/uhm_substation_bills
HECO_BILLS_ROOT = SCRIPT_DIR.parent.parent         # .../heco_bills  (where heco_common.py lives)

# ── Paths ──────────────────────────────────────────────────────────────
SOURCE_DIR = PROJECT_DIR / "input_bills"
ARCHIVE_DIR = PROJECT_DIR / "bill_archive"
DUPLICATE_DIR = SOURCE_DIR / "duplicate_bills"
OUTPUT_CSV = PROJECT_DIR / "output" / "substation_bills_data.csv"

# ── Filename ──────────────────────────────────────────────────────────
# Canonical format: ACCOUNTNUMBER_YYYY_MM_DD_substation_bill.pdf
FILENAME_SUFFIX = "substation_bill"

FILENAME_PATTERN = re.compile(
    r"^(?P<acct>\d+)_(?P<year>\d{4})_(?P<month>\d{2})_(?P<day>\d{2}).*\.pdf$",
    re.IGNORECASE,
)

# ── Database (step 3) ────────────────────────────────────────────────
DATABASE = "uhm2023"
TABLE = "substations.bill"
COLUMNS = [
    "date_from",
    "date_to",
    "kwh_512199",
    "kwh_517063",
    "kwh_517090",
    "kwh_623555",
    "kwh_623556",
    "kwh_623557",
    "customer_charge",
    "demand_charge",
    "non_fuel_energy_charge",
    "power_factor_adjustment",
    "rba_rate_adjustment",
    "irp_cost_recovery",
    "pbf_surcharge",
    "energy_cost_recovery",
    "purchased_power_adjustment",
    "renewable_infrastructure_pgm",
    "green_infrastructure_fee",
    "current_charges_total",
    "power_factor",
    '"billed_$"',
    "service_days",
    "billed_kwh",
    "kwh_day",
    "dollars_day",
    "blended_rate",
]

# ── Database (step 0) ─────────────────────────────────────────────────
# extracts/ is shared across all heco_bills projects, so it lives at the
# repo root next to heco_common.py, not inside uhm_substation_bills/.
EXTRACTS_DIR = HECO_BILLS_ROOT / "extracts"
MAX_DATE_QUERY = "SELECT max(date_to) FROM substations.bill"
MAX_DATE_CSV = EXTRACTS_DIR / "substation_bill_max_date.csv"


# ── PDF parsing (project-specific — every bill layout is different) ───

import pdfplumber
from datetime import date


def extract_bill_info(pdf_path):
    """
    Extract (account_number, 'YYYY_MM_DD') from a substation bill PDF.
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


def get_bill_date(pdf_path):
    """
    Extract the bill's Service Period end date as a datetime.date, for
    checking against extracts/substation_bill_max_date.csv (script 0).
    Matches what's stored in the database as date_to.
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = pdf.pages[0].extract_text()
            if not text:
                return None

            service_period_match = re.search(
                r"Service Period\s+\d{2}/\d{2}/\d{2}\s*-\s*(\d{2})/(\d{2})/(\d{2})", text
            )
            if not service_period_match:
                return None

            month, day, year_short = service_period_match.groups()
            return date(2000 + int(year_short), int(month), int(day))
    except Exception as e:
        print(f"  [ERROR] Reading {pdf_path.name}: {e}")
        return None
