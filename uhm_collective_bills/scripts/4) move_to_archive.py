from pathlib import Path
import shutil
import re

# ── Paths ──────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent

SOURCE_DIR = PROJECT_ROOT / "input_bills"

ARCHIVE_DIR = PROJECT_ROOT / "bill_archive"

# Example expected filename format:
# ACCOUNT_2025_03_15_heco_bill.pdf
pattern = re.compile(
    r"^(?P<acct>\d+)_(?P<year>\d{4})_(?P<month>\d{2})_(?P<day>\d{2}).*\.pdf$",
    re.IGNORECASE,
)


def get_fy(year: int, month: int) -> str:
    """
    FY logic:
    - Jul–Dec => next fiscal year
    - Jan–Jun => same fiscal year
    """
    if month >= 7:
        fy = year + 1
    else:
        fy = year

    return f"FY{str(fy)[-2:]}"


def move_bills_to_archive():
    # create archive folder if it doesn't exist
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    moved = 0
    skipped = 0

    for file in SOURCE_DIR.glob("*.pdf"):

        if not file.is_file():
            continue

        match = pattern.match(file.name)

        if not match:
            print(f"Skipping unmatched filename: {file.name}")
            skipped += 1
            continue

        year = int(match.group("year"))
        month = int(match.group("month"))

        fy_folder = get_fy(year, month)

        # create FY folder if it doesn't exist
        target_dir = ARCHIVE_DIR / fy_folder
        target_dir.mkdir(parents=True, exist_ok=True)

        destination = target_dir / file.name

        # avoid overwrite collisions
        if destination.exists():
            base = file.stem
            ext = file.suffix
            counter = 1

            while destination.exists():
                destination = target_dir / f"{base}_{counter}{ext}"
                counter += 1

        print(f"Moving {file.name} → {fy_folder}")
        shutil.move(str(file), str(destination))

        moved += 1

    print("\n--- Done ---")
    print(f"Moved: {moved} | Skipped: {skipped}")


if __name__ == "__main__":
    move_bills_to_archive()