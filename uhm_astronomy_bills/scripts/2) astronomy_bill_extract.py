"""
Extract information from astronomy bills

contract, date_end, kwh, cost$, and days columns
"""
from pydoc import text

import sys
import pdfplumber
import re
import os
import glob
import pandas as pd
from datetime import datetime
from pathlib import Path

# Import astronomy's paths/settings from config.py, the same way
# scripts 1) and 3) do — instead of hardcoding a server-only path here.
SCRIPT_DIR = Path(__file__).resolve().parent
HECO_BILLS_ROOT = SCRIPT_DIR.parent.parent   # heco_bills/  <- where heco_common.py lives
sys.path.insert(0, str(HECO_BILLS_ROOT))

import config

# folder path
input_folder = config.SOURCE_DIR

"""
we want to extract:
    - contract
    - date_end
    - kwh
    - cost $
    - days
"""

def extract_year_from_service_period(text):
    """Extract year from Service Period line like '11/26/25 - 12/26/25'"""
    match = re.search(r'Service Period\s+(\d{1,2}/\d{1,2}/(\d{2}))\s*-\s*(\d{1,2}/\d{1,2}/(\d{2}))', text)
    if match:
        # Get the year from the end date
        year_suffix = match.group(4)
        # Convert 2-digit year to 4-digit (assuming 20xx)
        year = f"20{year_suffix}"
        return year
    return None

def extract_contract_number(text):
    """
    Extract contract number from text
    Looks like:
    CONTRACT:
    XXXXXXXXXXXX
    """
    match = re.search( r'Invoice Number:.*?Contract:\s*\n\s*\d+\s+(\d+)', text, re.IGNORECASE)    
    
    if match:
        return match.group(1)

    return "UNKNOWN"

def extract_bill_period_end(text):
    """
    Extract bill period end date from text
    Looks like:
    FROM 03/18/26 TO 04/16/26 30 DAYS
    """
    bill_period_match = re.search(r'FROM\s+(\d{1,2}/\d{1,2}/\d{2})\s+TO\s+(\d{1,2}/\d{1,2}/\d{2})', text)
    date_end = None
    if bill_period_match:
        date_end = bill_period_match.group(2)  # Get the end date
    return date_end

def extract_days(text):
    """
    Extract days from text
    Looks like:
    FROM 03/18/26 TO 04/16/26  30 DAYS
    """
    
    days_match = re.search(r'FROM\s+\d{1,2}/\d{1,2}/\d{2}\s+TO\s+\d{1,2}/\d{1,2}/\d{2}\s+(\d+)\s+DAYS', text)

    if days_match:
        return int(days_match.group(1))
    return None

def extract_cost(text):
    """
    Extract cost from text
    Looks like:
    
    Current Charges Due 02/07/2026 $32,545.52
    TOTAL AMOUNT DUE $69,113.17

    OR

    Current Charges $31,632.22
    TOTAL AMOUNT DUE 03/10/2026 $31,632.22
    
    always want TOTAL AMOUNT DUE
    """
    
    # cost_match = re.search(r'TOTAL AMOUNT DUE\s+\d{1,2}/\d{1,2}/\d{4}\s+\$([\d,]+\.\d{2})', text)
    cost_match = re.search( r'TOTAL AMOUNT DUE\s+(?:\d{1,2}/\d{1,2}/\d{4}\s+)?\$([\d,]+\.\d{2})', text)
    if cost_match:
        # Remove commas from the cost string and convert to float
        cost_str = cost_match.group(1).replace(',', '')
        return float(cost_str)
    return None

def extract_kwh(text):
    """
    Extract kwh from text
    Looks like:
    DATE          KWH         AMOUNT      DAYS    KWH/DAY      $/DAY
    04/16/26      101813      $35,500.71  30      3,393.77     1,183.36
    """
    
    # kwh_match = re.search(r'\d{1,2}/\d{1,2}/\d{2}\s+(\d+)\s+\$[\d,]+\.\d{2}', text)
    kwh_match = re.search(r'\d{1,2}/\d{1,2}/\d{2}\s+(\d{5,7})', text)
    if kwh_match:
        return int(kwh_match.group(1))
    return None

def extract_text_from_pdf(pdf_path):
    """Extract all text from a PDF"""
    text = ""

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()

            if page_text:
                text += page_text + "\n"

    return text


def process_bills(input_folder):
    """
    Process all PDFs and save extracted data to CSV
    """

    records = []

    # Find all PDFs
    pdf_files = glob.glob(os.path.join(input_folder, "*.pdf"))

    for pdf_file in pdf_files:
        print(f"Processing: {pdf_file}")

        try:
            # Extract text
            text = extract_text_from_pdf(pdf_file)

            # Extract fields
            contract = extract_contract_number(text)
            date_end = extract_bill_period_end(text)
            kwh = extract_kwh(text)
            cost = extract_cost(text)
            days = extract_days(text)

            # Store row
            records.append({
                "contract": contract,
                "date_end": date_end,
                "kwh": kwh,
                "cost$": cost,
                "days": days
            })

        except Exception as e:
            print(f"Error processing {pdf_file}: {e}")

    # Create dataframe
    df = pd.DataFrame(records)

    # Output CSV path — from config.py, so it matches wherever
    # this project actually lives (laptop or server)
    output_csv = config.OUTPUT_CSV

    # Ensure output folder exists
    os.makedirs(os.path.dirname(output_csv), exist_ok=True)

    # Save CSV
    # Overwrites existing file automatically
    df.to_csv(output_csv, index=False)

    print(f"\nSaved CSV to: {output_csv}")

    return df

if __name__ == "__main__":
    df = process_bills(input_folder)
    print(df)