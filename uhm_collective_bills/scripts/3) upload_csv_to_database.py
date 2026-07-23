import subprocess
from pathlib import Path

r"""
Script that can call psql uhm2023 in the terminal to connect to the database and then
call the following command to upload the heco electric bills csv file to the database:
\copy heco.kwh(contract, date_end, kwh, "cost$", days) FROM '<output_csv>' CSV HEADER;
"""

# ── Paths ──────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent

OUTPUT_DIR = PROJECT_ROOT / "output"

OUTPUT_CSV = OUTPUT_DIR / "electric_bills_data.csv"

def upload_csv_to_database():
    copy_command = (
        r'\copy heco.kwh(contract, date_end, kwh, "cost$", days) '
        f"FROM '{OUTPUT_CSV.as_posix()}' CSV HEADER;"
    )

    command = [
        "psql",
        "uhm2023",
        "-c",
        copy_command,
        ]

    subprocess.run(command, check=True)
    
if __name__ == "__main__":
    upload_csv_to_database()
    
    

"""

Script verification methodology:

--- create new table in database with exact column names and column data types, but ignore the existing values ---

CREATE TABLE heco.kwh_test AS 
TABLE heco.kwh 
WITH NO DATA;

--- update the script above to upload into the test table ---
\copy heco.kwh_test(contract, date_end, kwh, "cost$", days) FROM 'heco_collective/heco_collective_bill/output/electric_bills_data.csv' CSV HEADER;

--- run the script ---

--- check if the values in electric_bills_data.csv is in the heco.kwh_test table ---

"""