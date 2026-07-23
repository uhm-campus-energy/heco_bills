"""
3) Upload substation bill data to the database, then archive the bills —
   but ONLY if the upload succeeded.

Only runs where psql can reach the database (the server) — not from a
laptop, same as script 0). Calls psql to \\copy the extracted CSV into
substations.bill; if that succeeds, moves the corresponding bills from
input_bills/ into bill_archive/FY<YY>/ (see heco_common.upload_and_archive).
If the upload fails, the bills are left in input_bills/ untouched so a
fix + re-run can't skip any bill's database row.

Paths/database/table/columns all come from config.py, same as script 1).
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

r"""
Script verification methodology:

--- create new table in database with exact column names and column data types, but ignore the existing values ---

CREATE TABLE substations.bill_test AS
TABLE substations.bill
WITH NO DATA;

--- update the script above to upload into the test table ---
\copy substations.bill_test(date_from, date_to, billed_kwh, "billed_$", account, blended_rate, service_days, kwh_day, dollars_day, customer_charge, demand_charge, non_fuel_energy_charge, power_factor, rba_rate_adjustment, irp_cost_recovery, pbf_surcharge, energy_cost_recovery, purchased_power_adjustment, renewable_infrastructure_pgm, green_infrastructure_fee, rba_rate_per_kwh, ecr_rate_per_kwh, ppa_rate_per_kwh, nec_rate_per_kwh, kwh_512199, kwh_517063, kwh_517090, kwh_623555, kwh_623556, kwh_623557, power_factor_adjustment) FROM '<output_csv>' CSV HEADER;

--- run the script ---

--- check if the values in substration_bills_data.csv is in the substations.bill_test table ---

--- delete table after testing ---

DROP TABLE IF EXISTS substations.bill_test;
"""
