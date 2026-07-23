import sys
import pdfplumber
import re
import os
import glob
import pandas as pd
from datetime import datetime
from pathlib import Path

# Import substation's paths/settings from config.py, the same way
# scripts 1) and 4) do — instead of hardcoding a server-only path here.
SCRIPT_DIR = Path(__file__).resolve().parent
HECO_BILLS_ROOT = SCRIPT_DIR.parent.parent   # heco_bills/  <- where heco_common.py lives
sys.path.insert(0, str(HECO_BILLS_ROOT))

import config

# Folder path
input_folder = config.SOURCE_DIR


def extract_service_period(text):
    m = re.search(r"Service Period\s+(\d{2}/\d{2}/\d{2})\s*-\s*(\d{2}/\d{2}/\d{2})", text)

    if m:
        return m.group(1), m.group(2)
    
    return None, None


def get_kwh_for_meter(all_text, meter_id):
    for line in all_text.split("\n"):

        if meter_id in line and "KWH" in line:
            numbers = re.findall(r"[\d,]+\.\d+", line)
            if numbers:
                return float(numbers[-1].replace(",", ""))

    return None


def compute_days(date_from, date_to):
    d1 = datetime.strptime(date_from, "%m/%d/%y").date()
    d2 = datetime.strptime(date_to, "%m/%d/%y").date()

    return (d2 - d1).days + 1


def parse_charges(text):
    patterns = {
        "Customer Charge": "customer_charge",
        "Demand Charge": "demand_charge",
        "Non-Fuel Energy Charge": "non_fuel_energy_charge",
        "Power Factor": "power_factor_adjustment",
        "RBA Rate Adjustment": "rba_rate_adjustment",
        "IRP Cost Recovery": "irp_cost_recovery",
        "PBF Surcharge": "pbf_surcharge",
        "Energy Cost Recovery": "energy_cost_recovery",
        "Purchased Power Adjustment": "purchased_power_adjustment",
        "Renewable Infrastructure Pgm": "renewable_infrastructure_pgm",
        "Green Infrastructure Fee": "green_infrastructure_fee",
        "Total for Current Charges": "current_charges_total",
    }

    out = {v: None for v in patterns.values()}
    out["power_factor"] = None

    for label, key in patterns.items():
        if label == "Power Factor":
            m = re.search(
                r"Power Factor\s*\((\d{2})\)\s*\x24([\d,]+\.\d+)", text)

            if m:
                out["power_factor"] = int(m.group(1))
                out[key] = -float(m.group(2).replace(",", ""))
        elif label == "Total for Current Charges":
            matches = re.findall(
                r"Total for Current Charges\s*\$([\d,]+\.\d+)", text)

            if matches:
                out[key] = float(matches[-1].replace(",", ""))
        else:
            m = re.search(
                rf"{re.escape(label)}\s*\$([\d,]+\.\d+)", text)

            if m:
                out[key] = float(m.group(1).replace(",", ""))

    return out


# meter mappings

meter_ids = {
    "MPX000512199": "kwh_512199",
    "MPX000517063": "kwh_517063",
    "MPX000517090": "kwh_517090",
    "MPX000623555": "kwh_623555",
    "MPX000623556": "kwh_623556",
    "MPX000623557": "kwh_623557",
}

# extraction

all_rows = []
pdf_files = glob.glob(os.path.join(input_folder, "*.pdf"))

for pdf_path in pdf_files:
    print("Processing:", pdf_path)

    with pdfplumber.open(pdf_path) as pdf:
        page1_text = pdf.pages[0].extract_text() or ""
        page5_text = pdf.pages[4].extract_text() or ""

        all_text = "\n".join(
            (p.extract_text() or "")
            for p in pdf.pages
        )

    date_from, date_to = extract_service_period(page1_text)
    charges = parse_charges(page5_text)
    current_charges_total = charges["current_charges_total"]

    meter_values = {
        colname: get_kwh_for_meter(all_text, meter_id)
        for meter_id, colname in meter_ids.items()
    }

    billed_kwh = sum(
        v for v in meter_values.values()
        if v is not None
    )

    service_days = compute_days(date_from, date_to)
    
    kwh_day = (
        round(billed_kwh / service_days)
        if billed_kwh and service_days
        else None
    )

    dollars_day = (
        round(current_charges_total / service_days, 2)
        if current_charges_total and service_days
        else None
    )

    blended_rate = (
        round(current_charges_total / billed_kwh, 15)
        if current_charges_total and billed_kwh
        else None
    )

    row = {
        "date_from": datetime.strptime(
            date_from,
            "%m/%d/%y"
        ).strftime("%Y-%m-%d"),
        "date_to": datetime.strptime(
            date_to,
            "%m/%d/%y"
        ).strftime("%Y-%m-%d"),
        **meter_values,
        **charges,
        "billed_$": current_charges_total,
        "service_days": service_days,
        "billed_kwh": billed_kwh,
        "kwh_day": kwh_day,
        "dollars_day": dollars_day,
        "blended_rate": blended_rate,
    }

    all_rows.append(row)

# Save CSV
df = pd.DataFrame(all_rows)

output_path = config.OUTPUT_CSV
os.makedirs(os.path.dirname(output_path), exist_ok=True)
df.to_csv(output_path, index=False)
print("\nSaved:", output_path)