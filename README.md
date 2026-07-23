# heco_bills

Scripts for processing UH Manoa's Hawaiian Electric (HECO) bills: renaming
and deduplicating PDF bills, extracting billing data into CSVs, uploading
that data to the `uhm2023` Postgres database, and archiving processed bills
by fiscal year.

There are three independent pipelines, one per billing account type:

| Project                | Database table     | Notes |
|-------------------------|---------------------|-------|
| `uhm_astronomy_bills`   | `heco.kwh`          | One account/contract per bill |
| `uhm_substation_bills`  | `substations.bill`  | One account, multiple meters per bill |
| `uhm_collective_bills`  | `heco.kwh`          | One PDF covers dozens of contracts (2-page block each) |

## Repo layout

```
heco_bills/
├── heco_common.py          # shared pipeline logic (see below)
├── extracts/                # CSVs pulled from the DB, used to skip already-billed PDFs
└── uhm_<project>_bills/
    ├── scripts/
    │   ├── config.py                        # paths, DB table/columns, PDF parsing (astronomy/substation)
    │   ├── 0) pre-process...py              # pull last billed date(s) from the DB
    │   ├── 1) organize_*_bills.py           # rename + dedupe incoming PDFs
    │   ├── 2) *_bill_extract.py             # extract billing data to CSV
    │   └── 3) upload_and_archive.py         # upload CSV to DB, then archive PDFs
    ├── input_bills/          # drop new PDF bills here (gitignored)
    │   └── duplicate_bills/  # bills skipped as duplicates/already billed
    ├── bill_archive/         # processed bills, sorted into FY<YY>/ (gitignored)
    └── output/               # extracted CSV output (gitignored)
```

`uhm_collective_bills` follows the same idea but predates `config.py` /
`heco_common.upload_and_archive`, so its steps 3 and 4 (upload, then
archive) are separate scripts instead of one combined step, and it has no
step 0 pre-process script.

PDF bills, extracted CSVs, and archives are all gitignored (see
`.gitignore`) since they may contain account data — only the scripts are
version controlled.

## Pipeline

Each project is run in numeric script order:

1. **`0) pre-process...`** *(astronomy, substation only; server-only, needs `psql` access to `uhm2023`)*
   Queries the database for the last billed date per contract (or overall
   max date, for substations) and writes it to `extracts/`. This lets step
   1 skip PDFs that are already in the database.

2. **`1) organize_*_bills.py`**
   Renames PDFs in `input_bills/` to the canonical format
   `ACCOUNTNUMBER_YYYY_MM_DD_<suffix>.pdf`, using account number and
   service-period-end date parsed from each PDF. Moves exact duplicates
   (by MD5 hash), bills already present in `bill_archive/`, and (if step 0
   was run) bills already covered by the database into
   `input_bills/duplicate_bills/`.

3. **`2) *_bill_extract.py`**
   Parses the remaining PDFs in `input_bills/` and writes billing data
   (contract, dates, kWh, cost, charges, etc. — columns vary by project)
   to `output/*.csv`.

4. **`3) upload_and_archive.py`**
   Uploads the CSV to the database via `psql \copy`. Only if that upload
   succeeds does it move the corresponding PDFs from `input_bills/` into
   `bill_archive/FY<YY>/` — a failed upload leaves the bills untouched so a
   fix-and-rerun can't silently skip a bill's database row.

   `uhm_collective_bills` instead runs `3) upload_csv_to_database.py` then
   `4) move_to_archive.py` as two separate scripts.

Fiscal year folders follow UH's fiscal year (Jul–Dec bills go to the
*next* FY, Jan–Jun bills stay in the *same* FY), e.g. a bill dated
`2025_08_15` archives to `bill_archive/FY26/`.

## `heco_common.py`

Shared logic used by all three pipelines (astronomy and substation via
`config.py`; collective directly): MD5 duplicate detection, canonical
renaming, archive duplicate checks, moving bills into `bill_archive/FY<YY>/`,
and uploading/extracting CSVs via `psql`. Each project supplies its own
`config.py` with paths, DB table/columns, and a PDF-parsing function, since
every bill layout differs. Fix a bug in `heco_common.py` once and all three
projects get the fix.

## Requirements

- Python 3 with `pdfplumber` and `pandas`
- `psql` on `PATH`, with access to the `uhm2023` database (steps 0 and 3
  only run where the database is reachable, e.g. the server — not
  necessarily a laptop)

## Usage

From a project's `scripts/` folder, run the numbered scripts in order,
e.g. for astronomy bills:

```
python "0) pre-process, find the last dates in database.py"
python "1) organize_astronomy_bills.py"
python "2) astronomy_bill_extract.py"
python "3) upload_and_archive.py"
```

`1) organize_*_bills.py` also accepts an optional folder argument to
process PDFs from somewhere other than `input_bills/`.
