import pandas as pd
import re
import os


def clean_vehicle_report(file_path: str, output_path: str = None) -> pd.DataFrame:
    """
    Clean up a vehicle report where carriers are section headers
    and convert it to a proper tabular format with carriers as a column.

    Args:
        file_path: Path to the Excel file
        output_path: Path to save the cleaned file (optional)

    Returns:
        pandas.DataFrame: Cleaned data
    """

    # Read the Excel file
    df_raw = pd.read_excel(file_path, header=None, engine='xlrd', dtype=str)
    df_raw = df_raw.fillna('')

    cleaned_data = []
    current_carrier = None

    # Process each row
    for idx, row in df_raw.iterrows():
        row_list = row.tolist()

        # Skip first few rows (title rows)
        if idx < 4:
            continue

        # Check if this is a carrier row
        carrier_info = extract_carrier_from_row(row_list)
        if carrier_info:
            current_carrier = carrier_info
            continue

        # Skip header rows
        if is_header_row(row_list):
            continue

        # Check if this is a vehicle data row
        if current_carrier and is_vehicle_data_row(row_list):
            vehicle_record = parse_vehicle_row(row_list, current_carrier)
            if vehicle_record:
                cleaned_data.append(vehicle_record)

    # Create DataFrame
    if cleaned_data:
        result_df = pd.DataFrame(cleaned_data)
        result_df = clean_data_types(result_df)
    else:
        result_df = pd.DataFrame()

    # Save to file if output path provided
    if output_path and not result_df.empty:
        result_df.to_excel(output_path, index=False)

    return result_df


def extract_carrier_from_row(row_list):
    """Extract carrier information from a row."""
    if len(row_list) < 6:
        return None

    col_b = str(row_list[1]).strip() if len(row_list) > 1 else ""
    col_f = str(row_list[5]).strip() if len(row_list) > 5 else ""

    # Must have both B and F columns filled
    if not col_b or not col_f:
        return None

    # Shouldn't have data in typical data columns (I, P)
    col_i = str(row_list[8]).strip() if len(row_list) > 8 else ""
    col_p = str(row_list[15]).strip() if len(row_list) > 15 else ""

    if col_i or col_p:
        return None

    # Skip header rows
    if any(word in col_b.lower() for word in ['vehicle', 'description']):
        return None
    if any(word in col_f.lower() for word in ['description', 'type', 'driver']):
        return None

    # Valid carrier format
    carrier_name = f"{col_b} {col_f}".strip()

    if len(carrier_name) > 3 and re.search(r'[A-Za-z0-9]', carrier_name):
        return carrier_name

    return None


def is_header_row(row_list):
    """Check if a row contains column headers."""
    row_text = ' '.join([str(cell).lower() for cell in row_list[:20]])
    header_indicators = ['vehicle', 'description',
                         'type', 'driver', 'license', 'tare']
    matches = sum(
        1 for indicator in header_indicators if indicator in row_text)
    return matches >= 3


def is_vehicle_data_row(row_list):
    """Check if a row contains vehicle data."""
    # Must have vehicle identifier in column B
    col_b = str(row_list[1]).strip() if len(row_list) > 1 else ""
    if not col_b:
        return False

    # Must have type in column I
    col_i = str(row_list[8]).strip() if len(row_list) > 8 else ""
    if not col_i:
        return False

    # Must have tare weight in column P
    col_p = str(row_list[15]).strip() if len(row_list) > 15 else ""
    if not col_p:
        return False

    # Skip obvious header rows
    if any(word in col_b.lower() for word in ['vehicle', 'description', 'type']):
        return False

    return True


def combine_time_and_date(time_str: str, date_str: str) -> str:
    """
    Combine time and date strings properly.
    Input: time_str like "10:32:29", date_str like "1997-11-06 00:00:00"
    Output: "1997-11-06 10:32:29"
    """
    if not time_str and not date_str:
        return ''

    # Clean up the strings
    time_str = str(time_str).strip()
    date_str = str(date_str).strip()

    # Extract just the date part (remove time if present)
    if date_str and ' ' in date_str:
        date_part = date_str.split(' ')[0]  # Get just "1997-11-06"
    else:
        date_part = date_str

    # Extract just the time part (remove date if present)
    if time_str and ' ' in time_str:
        time_part = time_str.split(' ')[-1]  # Get the time part
    else:
        time_part = time_str

    # Combine them properly
    if date_part and time_part:
        # Check if time_part looks like a valid time (has colons)
        if ':' in time_part:
            return f"{date_part} {time_part}"
        else:
            return date_part
    elif date_part:
        return date_part
    elif time_part and ':' in time_part:
        return time_part
    else:
        return ''

# Then update the parsing section to:


def parse_vehicle_row(row_list, carrier):
    """Parse a vehicle data row according to the column structure."""
    # Ensure we have enough columns
    while len(row_list) < 30:
        row_list.append('')

    record = {
        'Carrier': carrier,
        'Vehicle': str(row_list[1]).strip(),  # Column B
        'Description': str(row_list[3]).strip(),  # Column D
        'Type': str(row_list[8]).strip(),  # Column I
        'Driver': str(row_list[12]).strip(),  # Column M
        'License': str(row_list[13]).strip(),  # Column N
        'Tare': str(row_list[15]).strip(),  # Column P
    }

    # Parse time data with proper combination
    time_tare_time = str(row_list[18]).strip() if len(
        row_list) > 18 else ''  # Column S
    time_tare_date = str(row_list[21]).strip() if len(
        row_list) > 21 else ''  # Column V
    time_load_time = str(row_list[22]).strip() if len(
        row_list) > 22 else ''  # Column W
    time_load_date = str(row_list[24]).strip() if len(
        row_list) > 24 else ''  # Column Y

    # Combine time and date fields properly
    record['Time_Tare'] = combine_time_and_date(time_tare_time, time_tare_date)
    record['Time_Load'] = combine_time_and_date(time_load_time, time_load_date)

    return record


def clean_data_types(df):
    """Clean up data types in the DataFrame."""
    if df.empty:
        return df

    # Convert tare to numeric
    if 'Tare' in df.columns:
        df['Tare'] = pd.to_numeric(df['Tare'], errors='coerce')

    # Clean up text columns
    text_columns = ['Carrier', 'Vehicle',
                    'Description', 'Type', 'Driver', 'License']
    for col in text_columns:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
            df[col] = df[col].replace('nan', '')

    return df


def validate_extraction(file_path: str, cleaned_df: pd.DataFrame):
    """
    Validate that we captured all the data correctly by comparing 
    raw file counts vs processed counts.
    """
    print("VALIDATION REPORT")

    # Read raw file for comparison
    df_raw = pd.read_excel(file_path, header=None, engine='xlrd', dtype=str)
    df_raw = df_raw.fillna('')

    # Count potential vehicle data rows in raw file
    raw_vehicle_rows = []
    raw_carriers = []
    missing_carrier_vehicles = []  # Vehicles without carriers above them

    current_carrier = None

    for idx, row in df_raw.iterrows():
        row_list = row.tolist()

        if idx < 4:  # Skip title rows
            continue

        # Check for carriers
        carrier = extract_carrier_from_row(row_list)
        if carrier:
            current_carrier = carrier
            raw_carriers.append((idx, carrier))
            continue

        # Check for potential vehicle data (has vehicle ID + type + tare)
        if is_potential_vehicle_row(row_list):
            vehicle_data = {
                'row': idx + 1,  # Excel row number (1-based)
                'vehicle': str(row_list[1]).strip() if len(row_list) > 1 else '',
                'type': str(row_list[8]).strip() if len(row_list) > 8 else '',
                'tare': str(row_list[15]).strip() if len(row_list) > 15 else '',
                'carrier': current_carrier
            }

            raw_vehicle_rows.append(vehicle_data)

            # Track orphaned vehicles (no carrier above them)
            if not current_carrier:
                missing_carrier_vehicles.append(vehicle_data)

    # Compare counts
    print(f"Raw file analysis:")
    print(f"  Total carriers found: {len(raw_carriers)}")
    print(f"  Total potential vehicle rows: {len(raw_vehicle_rows)}")
    print(f"  No Carrier Vehicles: {len(missing_carrier_vehicles)}")

    print(f"\nProcessed data:")
    print(
        f"  Carriers processed: {cleaned_df['Carrier'].nunique() if not cleaned_df.empty else 0}")
    print(
        f"  Vehicle records extracted: {len(cleaned_df) if not cleaned_df.empty else 0}")

    # Show missing carrier vehicles
    if missing_carrier_vehicles:
        print(f"\n Missing Carrier Vehicles (not captured):")
        print("Row | Vehicle | Type | Tare")
        print("-" * 30)
        for vehicle in missing_carrier_vehicles[:10]:  # Show first 10
            print(
                f"{vehicle['row']:3} | {vehicle['vehicle']:7} | {vehicle['type']:6} | {vehicle['tare']}")
        if len(missing_carrier_vehicles) > 10:
            print(f"... and {len(missing_carrier_vehicles) - 10} more")

    # Check for missed vehicles (vehicles that should have been captured but weren't)
    if not cleaned_df.empty:
        # This is approximate since we don't track original row numbers in cleaned data
        vehicles_with_carriers = [v for v in raw_vehicle_rows if v['carrier']]
        missed_count = len(vehicles_with_carriers) - len(cleaned_df)

        if missed_count > 0:
            print(
                f"\nPOTENTIALLY MISSED: ~{missed_count} vehicles with carriers weren't captured")
        else:
            print(f"\nSUCCESS: All vehicles with carriers appear to be captured")

    return {
        'raw_carriers': len(raw_carriers),
        'raw_vehicles': len(raw_vehicle_rows),
        'missing_carrier_vehicles': len(missing_carrier_vehicles),
        'processed_vehicles': len(cleaned_df) if not cleaned_df.empty else 0,
        'missing_carrier_vehicles_details': missing_carrier_vehicles
    }


def is_potential_vehicle_row(row_list):
    """
    More lenient check for potential vehicle data rows 
    (doesn't require all fields like the main processor does)
    """
    if len(row_list) < 16:
        return False

    # Has something in vehicle column (B)
    col_b = str(row_list[1]).strip() if len(row_list) > 1 else ""
    if not col_b or col_b.lower() in ['vehicle', 'nan']:
        return False

    # Has either type (I) or tare (P)
    col_i = str(row_list[8]).strip() if len(row_list) > 8 else ""
    col_p = str(row_list[15]).strip() if len(row_list) > 15 else ""

    if not col_i and not col_p:
        return False

    # Skip header rows
    if any(word in col_b.lower() for word in ['vehicle', 'description', 'type']):
        return False

    return True


# Run Script
if __name__ == "__main__":
    input_file = "c:\\Users\\aschwindt\\Downloads\\Vehicle Report.xls"
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Navigate to the reports folder relative to the script location
    reports_dir = os.path.join(script_dir, "..", "reports")
    output_file = os.path.join(reports_dir, "Vehicle_Report_Processed.xlsx")

    # Create reports directory if it doesn't exist
    os.makedirs("../reports", exist_ok=True)

    # Process the file
    cleaned_df = clean_vehicle_report(input_file, output_file)

    # Run validation
    validation_results = validate_extraction(input_file, cleaned_df)

    print(f"\nSUMMARY")
    print(
        f"Processed {len(cleaned_df)} records from {cleaned_df['Carrier'].nunique()} carriers")
    if validation_results['missing_carrier_vehicles'] > 0:
        print(
            f"{validation_results['missing_carrier_vehicles']} Vehicles not captured with missing carrier above them")
