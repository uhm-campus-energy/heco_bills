"""
Electric Bill PDF Data Extractor
Extracts contract, date_end, kwh, cost$, and days from Hawaiian Electric bills
"""

import pdfplumber
import pandas as pd
import re
from datetime import datetime
from pathlib import Path
import sys

# ── Paths ──────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent

SOURCE_DIR = PROJECT_ROOT / "input_bills"

OUTPUT_DIR = PROJECT_ROOT / "output"

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

def parse_bill_period_date(date_str, year):
    """Convert date like '12/15' to '12/15/25' format"""
    if not date_str or not year:
        return None
    
    # Extract month and day
    match = re.match(r'(\d{1,2})/(\d{1,2})', date_str)
    if match:
        month = match.group(1)
        day = match.group(2)
        # Use last 2 digits of year
        year_suffix = year[-2:]
        return f"{month}/{day}/{year_suffix}"
    return None

def extract_contract_data(pdf_path):
    """Extract data for all contracts from a single PDF"""
    contracts_data = []
    
    with pdfplumber.open(pdf_path) as pdf:
        # First, get the year from the first page's Service Period
        first_page_text = pdf.pages[0].extract_text()
        year = extract_year_from_service_period(first_page_text)
        
        if not year:
            print(f"Warning: Could not extract year from {pdf_path}")
            year = "2025"  # Default fallback
        
        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text()
            
            if not text:
                continue
            
            # Look for Account Number (CONTRACT ACCT) - 12 digits
            account_check = re.search(r'(\d{12})', text)
            if not account_check:
                continue
            
            account_num = account_check.group(1)
            
            # Skip if this is the collective summary page (301501010195)
            if account_num == "301501010195":
                continue
            
            # Extract the 8-digit Contract # 
            # It appears after "Contract:" or on the line with Invoice Number
            # Pattern: "Invoice Number: Contract:" followed by next line with "123456789 32045047"
            contract = None
            
            # Try to find the pattern: Invoice Number then Contract (8 digits)
            invoice_contract = re.search(r'Invoice Number:.*?Contract:.*?\n\s*(\d{9})\s+(\d{8})', text, re.DOTALL)
            if invoice_contract:
                contract = invoice_contract.group(2)  # The 8-digit contract number
            
            # Backup method: look for "Contract:" followed by 8 digits
            if not contract:
                contract_match = re.search(r'Contract:\s*\n?\s*(\d{8})', text)
                if contract_match:
                    contract = contract_match.group(1)
            
            if not contract:
                continue
            
            # Extract Bill Period to get the end date
            bill_period_match = re.search(r'FROM\s+(\d{1,2}/\d{1,2}/\d{2})\s+TO\s+(\d{1,2}/\d{1,2}/\d{2})', text)
            date_end = None
            days = None
            
            if bill_period_match:
                end_date_str = bill_period_match.group(2)
                date_end = end_date_str
                
                # Extract days - it appears right after the date range
                days_match = re.search(r'FROM\s+\d{1,2}/\d{1,2}/\d{2}\s+TO\s+\d{1,2}/\d{1,2}/\d{2}\s+(\d+)\s+DAYS', text)
                if days_match:
                    days = int(days_match.group(1))
            
            # Extract kWh from USAGE PROFILE table
            kwh = None
            # Look for the pattern: date kwh $amount days
            # The first line after "DATE KWH AMOUNT DAYS" header
            usage_match = re.search(r'(\d{1,2}/\d{1,2}/\d{2})\s+(\d+)\s+\$([0-9,]+\.\d{2})\s+(\d+)', text)
            if usage_match:
                kwh = int(usage_match.group(2))
            
            # Extract cost from TOTAL AMOUNT DUE
            cost = None
            cost_match = re.search(r'TOTAL AMOUNT DUE.*?\$([0-9,]+\.\d{2})', text)
            if cost_match:
                cost_str = cost_match.group(1).replace(',', '')
                cost = float(cost_str)
            
            # Only add if we have the essential data
            if contract and date_end and kwh is not None and cost is not None and days is not None:
                contracts_data.append({
                    'contract': contract,
                    'date_end': date_end,
                    'kwh': kwh,
                    'cost$': cost,
                    'days': days
                })
                print(f"  Extracted: Contract {contract}, Date: {date_end}, kWh: {kwh}, Cost: ${cost}, Days: {days}")
    
    return contracts_data

def process_pdfs(pdf_folder, output_csv):
    """Process all PDFs in a folder and create CSV"""
    pdf_folder = Path(pdf_folder)
    
    if not pdf_folder.exists():
        print(f"Error: Folder {pdf_folder} does not exist")
        return
    
    # Get all PDF files
    pdf_files = sorted(pdf_folder.glob("*.pdf"))
    
    if not pdf_files:
        print(f"No PDF files found in {pdf_folder}")
        return
    
    print(f"Found {len(pdf_files)} PDF files")
    
    all_data = []
    
    for pdf_file in pdf_files:
        print(f"\nProcessing: {pdf_file.name}")
        try:
            contracts = extract_contract_data(pdf_file)
            all_data.extend(contracts)
        except Exception as e:
            print(f"  Error processing {pdf_file.name}: {e}")
    
    if not all_data:
        print("\nNo data extracted from any PDFs")
        return
    
    # Create DataFrame and save to CSV
    df = pd.DataFrame(all_data)
    
    # Remove duplicates (in case same contract appears in multiple PDFs)
    df = df.drop_duplicates(subset=['contract', 'date_end'])
    
    # Sort by contract and date
    df = df.sort_values(['contract', 'date_end'])
    
    # Save to CSV
    df.to_csv(output_csv, index=False)
    print(f"\n{'='*60}")
    print(f"Success! Extracted {len(df)} unique contract records")
    print(f"Output saved to: {output_csv}")
    print(f"{'='*60}")
    print("\nFirst few rows:")
    print(df.head(10).to_string(index=False))

def main():
    """Main function"""
    # Allow command line override or use default
    if len(sys.argv) >= 2:
        pdf_folder = sys.argv[1]
    else:
        pdf_folder = SOURCE_DIR
        print(f"Using default folder: {pdf_folder}")

    # Set output CSV to same folder as input
    if len(sys.argv) >= 3:
        output_csv = sys.argv[2]
    else:
        OUTPUT_DIR.mkdir(exist_ok=True)
        output_csv = OUTPUT_DIR / "electric_bills_data.csv"
        print(f"Output will be saved to: {output_csv}")

    process_pdfs(pdf_folder, output_csv)

if __name__ == "__main__":
    main()