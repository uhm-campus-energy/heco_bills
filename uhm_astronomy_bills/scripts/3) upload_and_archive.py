"""
3) Upload astronomy bill data to the database, then archive the bills —
   but ONLY if the upload succeeded.
"""

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
HECO_BILLS_ROOT = SCRIPT_DIR.parent.parent   # heco_bills/  <- where heco_common.py lives
sys.path.insert(0, str(HECO_BILLS_ROOT))

import config
from heco_common import upload_and_archive


if __name__ == "__main__":
    upload_and_archive(
        database=config.DATABASE,
        table=config.TABLE,
        columns=config.COLUMNS,
        csv_path=config.OUTPUT_CSV,
        source_dir=config.SOURCE_DIR,
        archive_dir=config.ARCHIVE_DIR,
        filename_pattern=config.FILENAME_PATTERN,
    )
