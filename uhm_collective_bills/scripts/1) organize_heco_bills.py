"""
HECO Bill Organizer

Pipeline:
---------
1. Rename bills into canonical format
2. Detect duplicates across:
      - input_bills
      - archive FY folders
3. Move duplicates into duplicate_bills
4. Leave only unique bills for extraction

Filename format:
----------------
    ACCOUNTNUMBER_YYYY_MM_DD_heco_bill.pdf

Example:
--------
    123456789012_2025_10_31_heco_bill.pdf
"""

import pdfplumber
import re
import shutil
import hashlib
import sys
from datetime import date
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent

HECO_BILLS_ROOT = PROJECT_ROOT.parent   # heco_bills/  <- where heco_common.py lives
sys.path.insert(0, str(HECO_BILLS_ROOT))

from heco_common import load_max_dates

SOURCE_DIR = PROJECT_ROOT / "input_bills"

ARCHIVE_DIR = PROJECT_ROOT / "bill_archive"

DUPLICATE_DIR = SOURCE_DIR / "duplicate_bills"

LAST_DATES_CSV = HECO_BILLS_ROOT / "extracts" / "dates_heco_direct_bills.csv"

# ── Helpers ────────────────────────────────────────────────────────────────────

def get_pdf_hash(pdf_path):
    """
    Calculate MD5 hash for exact duplicate detection.
    """

    md5_hash = hashlib.md5()

    with open(pdf_path, "rb") as f:

        for chunk in iter(lambda: f.read(4096), b""):
            md5_hash.update(chunk)

    return md5_hash.hexdigest()


def extract_bill_info(pdf_path):
    """
    Extract:
        - account number
        - service period end date

    Returns:
        (account_number, YYYY_MM_DD)
    """

    try:

        with pdfplumber.open(pdf_path) as pdf:

            first_page = pdf.pages[0]

            text = first_page.extract_text()

            if not text:
                return None, None

            # ── Account Number ────────────────────────────────────────────────

            account_match = re.search(
                r'Account Number:.*?(\d{12})',
                text,
                re.DOTALL
            )

            account_number = (
                account_match.group(1)
                if account_match else None
            )

            # ── Service Period End Date ──────────────────────────────────────

            service_period_match = re.search(
                r'Service Period\s+\d{1,2}/\d{1,2}/\d{2}\s*-\s*(\d{1,2})/(\d{1,2})/(\d{2})',
                text
            )

            if service_period_match:

                month = service_period_match.group(1).zfill(2)

                day = service_period_match.group(2).zfill(2)

                year_short = service_period_match.group(3)

                year = f"20{year_short}"

                date_str = f"{year}_{month}_{day}"

            else:
                date_str = None

            return account_number, date_str

    except Exception as e:

        print(f"  [ERROR] Reading {pdf_path.name}: {e}")

        return None, None


def extract_all_contract_dates(pdf_path):
    """
    Extract {contract: bill_date} for every contract in a collective bill
    PDF -- unlike astronomy, one collective PDF covers dozens of separate
    contracts (one 2-page block each), each with its own bill period end
    date. The master account's own pages (no "Contract:" label) are
    skipped, same as step 2's extractor.
    """

    contract_dates = {}

    try:

        with pdfplumber.open(pdf_path) as pdf:

            for page in pdf.pages:

                text = page.extract_text()

                if not text:
                    continue

                contract_match = re.search(
                    r'Invoice Number:.*?Contract:\s*\n\s*\d+\s+(\d+)',
                    text,
                    re.DOTALL
                )

                if not contract_match:
                    continue

                contract = contract_match.group(1)

                bill_period_match = re.search(
                    r'FROM\s+\d{1,2}/\d{1,2}/\d{2}\s+TO\s+(\d{1,2})/(\d{1,2})/(\d{2})',
                    text
                )

                if not bill_period_match:
                    continue

                month, day, year_short = bill_period_match.groups()

                bill_date = date(2000 + int(year_short), int(month), int(day))

                contract_dates[contract] = bill_date

    except Exception as e:

        print(f"  [ERROR] Reading {pdf_path.name}: {e}")

    return contract_dates


def filter_already_billed(pdf_files, max_dates):
    """
    Move collective bills to duplicate_bills when EVERY contract inside is
    already <= the recorded max date for that contract in the database --
    i.e. this file has nothing new to add for any contract.

    If even one contract has a newer bill_date (or no recorded max date at
    all), the whole file is kept, since a collective PDF can't be split
    apart at this stage.

    Returns the remaining pdf_files (files not moved).
    """

    remaining = []

    for pdf_file in pdf_files:

        contract_dates = extract_all_contract_dates(pdf_file)

        fully_billed = contract_dates and all(
            max_dates.get(contract) is not None and bill_date <= max_dates[contract]
            for contract, bill_date in contract_dates.items()
        )

        if fully_billed:

            print(f"\nAll {len(contract_dates)} contract(s) already in database:")
            print(f"  {pdf_file.name}")

            move_to_duplicates(pdf_file)

            continue

        remaining.append(pdf_file)

    return remaining


def build_canonical_name(account_number, date_str):
    """
    Build canonical HECO filename.
    """

    return f"{account_number}_{date_str}_heco_bill.pdf"


def bill_exists_in_archive(filename):
    """
    Check if canonical filename already exists
    in any FY archive folder.
    """

    if not ARCHIVE_DIR.exists():
        return False

    for fy_folder in ARCHIVE_DIR.iterdir():

        if not fy_folder.is_dir():
            continue

        archive_file = fy_folder / filename

        if archive_file.exists():
            return True

    return False


def move_to_duplicates(file_path):
    """
    Move duplicate file into duplicate_bills folder.

    Handles collisions safely.
    """

    DUPLICATE_DIR.mkdir(exist_ok=True)

    dst_path = DUPLICATE_DIR / file_path.name

    counter = 1

    while dst_path.exists():

        dst_path = DUPLICATE_DIR / (
            f"{file_path.stem}_{counter}{file_path.suffix}"
        )

        counter += 1

    shutil.move(str(file_path), str(dst_path))

    print(f"  → DUPLICATE moved to: {dst_path.name}")


# ── Main Organizer ─────────────────────────────────────────────────────────────

def organize_bills(folder_path):

    folder = Path(folder_path)

    if not folder.exists():

        print(f"[ERROR] Folder does not exist:\n  {folder}")

        return

    DUPLICATE_DIR.mkdir(exist_ok=True)

    print(f"Processing PDFs in: {folder}")
    print(f"Duplicate folder: {DUPLICATE_DIR}\n")

    # ── Get PDFs in input folder only ─────────────────────────────────────────

    pdf_files = [

        f for f in folder.glob("*.pdf")

        if f.parent == folder
    ]

    if not pdf_files:

        print("No PDF files found.")

        return

    print(f"Found {len(pdf_files)} PDF file(s)\n")

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 0 — Skip bills already fully in the database
    # ──────────────────────────────────────────────────────────────────────────

    print("=" * 70)
    print("STEP 0: Check contracts against database (extracts/dates_heco_direct_bills.csv)")
    print("=" * 70)

    max_dates = load_max_dates(LAST_DATES_CSV)

    pdf_files = filter_already_billed(pdf_files, max_dates)

    if not pdf_files:

        print("\nNo new PDF files left to process.")

        return

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 1 — Analyze files
    # ──────────────────────────────────────────────────────────────────────────

    print("=" * 70)
    print("STEP 1: Analyze PDFs")
    print("=" * 70)

    file_info = {}

    hash_map = {}

    for pdf_file in pdf_files:

        print(f"\nProcessing: {pdf_file.name}")

        # ── Extract metadata ─────────────────────────────────────────────────

        account_number, date_str = extract_bill_info(pdf_file)

        print(f"  Account: {account_number}")
        print(f"  Date:    {date_str}")

        if not account_number or not date_str:

            print("  → Missing metadata")

            file_info[pdf_file] = {
                "valid": False
            }

            continue

        # ── Canonical filename ───────────────────────────────────────────────

        canonical_name = build_canonical_name(
            account_number,
            date_str
        )

        # ── Hash ─────────────────────────────────────────────────────────────

        file_hash = get_pdf_hash(pdf_file)

        print(f"  Hash:    {file_hash[:12]}...")

        file_info[pdf_file] = {
            "valid": True,
            "account": account_number,
            "date": date_str,
            "canonical_name": canonical_name,
            "hash": file_hash,
        }

        # exact duplicate tracking
        if file_hash not in hash_map:
            hash_map[file_hash] = []

        hash_map[file_hash].append(pdf_file)

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 2 — Move exact hash duplicates
    # ──────────────────────────────────────────────────────────────────────────

    print("\n" + "=" * 70)
    print("STEP 2: Move exact duplicate PDFs")
    print("=" * 70)

    duplicates_moved = 0

    for file_hash, files in hash_map.items():

        if len(files) <= 1:
            continue

        print(f"\nFound {len(files)} identical files")

        # keep first
        keep_file = files[0]

        print(f"  Keeping: {keep_file.name}")

        duplicate_files = files[1:]

        for dup_file in duplicate_files:

            info = file_info.get(dup_file)

            try:

                if info and info.get("valid"):

                    canonical_name = info["canonical_name"]

                    temp_path = dup_file.parent / canonical_name

                    # rename before moving
                    if dup_file.name != canonical_name:

                        if temp_path.exists():
                            temp_path = dup_file.parent / (
                                f"TEMP_{dup_file.name}"
                            )

                        dup_file.rename(temp_path)

                        dup_file = temp_path

                move_to_duplicates(dup_file)

                duplicates_moved += 1

            except Exception as e:

                print(f"  [ERROR] Moving duplicate: {e}")

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 3 — Rename + Archive duplicate detection
    # ──────────────────────────────────────────────────────────────────────────

    print("\n" + "=" * 70)
    print("STEP 3: Rename files")
    print("=" * 70)

    renamed_count = 0
    skipped_count = 0

    for pdf_file, info in file_info.items():

        # already moved
        if not pdf_file.exists():
            continue

        if not info.get("valid"):

            print(f"\nSkipping invalid file: {pdf_file.name}")

            skipped_count += 1

            continue

        canonical_name = info["canonical_name"]

        canonical_path = pdf_file.parent / canonical_name

        # ── Check archive duplicates ─────────────────────────────────────────

        duplicate_in_archive = bill_exists_in_archive(
            canonical_name
        )

        if duplicate_in_archive:

            print(f"\nDuplicate found in archive:")
            print(f"  {canonical_name}")

            # rename first
            if pdf_file.name != canonical_name:

                temp_path = canonical_path

                counter = 1

                while temp_path.exists():

                    temp_path = pdf_file.parent / (
                        f"{canonical_path.stem}_TEMP{counter}.pdf"
                    )

                    counter += 1

                pdf_file.rename(temp_path)

                pdf_file = temp_path

            move_to_duplicates(pdf_file)

            duplicates_moved += 1

            continue

        # ── Already correctly named ─────────────────────────────────────────

        if pdf_file.name == canonical_name:

            print(f"\nAlready correctly named:")
            print(f"  {pdf_file.name}")

            continue

        # ── Rename ──────────────────────────────────────────────────────────

        try:

            pdf_file.rename(canonical_path)

            print(f"\nRenamed:")
            print(f"  From: {pdf_file.name}")
            print(f"  To:   {canonical_name}")

            renamed_count += 1

        except Exception as e:

            print(f"\n[ERROR] Renaming {pdf_file.name}: {e}")

            skipped_count += 1

    # ──────────────────────────────────────────────────────────────────────────
    # Summary
    # ──────────────────────────────────────────────────────────────────────────

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    print(f"Total PDFs processed: {len(pdf_files)}")
    print(f"Duplicates moved:     {duplicates_moved}")
    print(f"Files renamed:        {renamed_count}")
    print(f"Files skipped:        {skipped_count}")

    print(f"\nDuplicate folder:")
    print(f"  {DUPLICATE_DIR}")

    print("=" * 70)


# ── Main ───────────────────────────────────────────────────────────────────────

def main():

    import sys

    folder = (
        sys.argv[1]
        if len(sys.argv) > 1
        else str(SOURCE_DIR)
    )

    print("HECO Bill Organizer")
    print("=" * 70)

    print(f"Working folder:\n  {folder}\n")

    organize_bills(folder)


if __name__ == "__main__":
    main()