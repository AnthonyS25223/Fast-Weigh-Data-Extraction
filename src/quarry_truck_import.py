import pandas as pd
from openpyxl import load_workbook
from fuzzywuzzy import fuzz


def normalize_phone(phone):
    """Remove non-numeric characters from phone numbers for comparison."""
    if pd.isna(phone):
        return ""
    return ''.join(filter(str.isdigit, str(phone)))


def normalize_name(name):
    """Normalize name by removing special characters and extra spaces for comparison."""
    if pd.isna(name):
        return ""

    # Convert to string and uppercase
    normalized = str(name).upper()

    # Remove common punctuation and special characters
    chars_to_remove = ['-', '_', '.', ',', "'", '"', '/', '\\', '&']
    for char in chars_to_remove:
        normalized = normalized.replace(char, ' ')

    # Replace multiple spaces with single space and strip
    normalized = ' '.join(normalized.split())

    return normalized


def is_soft_match(name1, name2, phone1, phone2, name_threshold=85):
    """Check if two records are a soft match based on name and phone similarity."""
    # Normalize phones
    p1 = normalize_phone(phone1)
    p2 = normalize_phone(phone2)

    # Normalize names for comparison
    n1 = normalize_name(name1)
    n2 = normalize_name(name2)

    # Check name similarity using normalized names
    name_score = fuzz.ratio(n1, n2)

    # Check if names are the same words but in different order
    words1 = sorted(n1.split())
    words2 = sorted(n2.split())
    words_match = words1 == words2 and len(words1) > 0

    # Strong soft match: similar names AND matching phones
    phones_match = p1 == p2 and p1 != ""
    names_similar = name_score >= name_threshold or words_match

    return names_similar and phones_match


def match_truck_to_hauler(truck_carrier, truck_name, truck_phone, hauler_df):
    """
    Match a truck record to a hauler using the same logic as hauler deduplication.

    Args:
        truck_carrier: Carrier from truck record
        truck_name: Name from truck record (extracted from "Carrier" column)
        truck_phone: Phone from truck record
        hauler_df: DataFrame of haulers with Temp_Hauler_ID

    Returns:
        Temp_Hauler_ID if match found, None otherwise
    """

    for idx in range(len(hauler_df)):
        hauler_carrier = hauler_df.loc[idx, 'Carrier']
        hauler_name = hauler_df.loc[idx, 'Name']
        hauler_phone = hauler_df.loc[idx,
                                     'Phone'] if 'Phone' in hauler_df.columns else ""

        # Check if carriers match
        carriers_match = str(truck_carrier).strip().upper() == str(
            hauler_carrier).strip().upper()

        # Check if names are the same words in different order
        truck_words = sorted(normalize_name(truck_name).split())
        hauler_words = sorted(normalize_name(hauler_name).split())
        words_match = truck_words == hauler_words and len(
            truck_words) > 0 and carriers_match

        # Check for exact match
        exact_match = normalize_name(truck_name) == normalize_name(
            hauler_name) and carriers_match

        # Check for soft match (similar names + matching phones)
        soft_match = is_soft_match(
            truck_name, hauler_name, truck_phone, hauler_phone) and carriers_match

        if exact_match or soft_match or words_match:
            return hauler_df.loc[idx, 'Temp_Hauler_ID']

    return None


def process_quarry_truck_data(truck_file, hauler_file, output_file=None):
    """
    Filter Quarry Truck data and assign Temp_Hauler_IDs from the Hauler dataset.

    Args:
        truck_file: Path to Quarry Truck Import Excel file
        hauler_file: Path to Quarry Hauler Import Excel file
        output_file: Path to save the processed Excel file (if None, overwrites truck_file)
    """

    if output_file is None:
        output_file = truck_file

    print("Loading Quarry Truck Master Data Set...")
    truck_df = pd.read_excel(truck_file, sheet_name="Master Data Set")

    print(f"Total truck records in Master Data Set: {len(truck_df)}")

    print("\nLoading Quarry Hauler Scrubbed Data Set...")
    hauler_df = pd.read_excel(hauler_file, sheet_name="Scrubbed Data Set")

    print(f"Total hauler records loaded: {len(hauler_df)}")

    # Check if Time_Load column exists
    if 'Time_Load' not in truck_df.columns:
        print("Error: 'Time_Load' column not found in Master Data Set")
        return None

    # Create a copy for the scrubbed dataset
    scrubbed_df = truck_df.copy()

    print("\n=== STEP 1: Filtering records by load time ===")

    # Count records before filtering
    initial_count = len(scrubbed_df)

    # Filter out system default "00:00:00 00:00:00"
    default_mask = scrubbed_df['Time_Load'].astype(
        str).str.strip() == '00:00:00 00:00:00'
    default_count = default_mask.sum()
    scrubbed_df = scrubbed_df[~default_mask]

    print(
        f"  Removed {default_count} records with system default time (00:00:00 00:00:00)")

    # Convert Time_Load to datetime for date filtering
    scrubbed_df['Time_Load'] = pd.to_datetime(
        scrubbed_df['Time_Load'], errors='coerce')

    # Filter out records before 2021
    cutoff_date = pd.Timestamp('2021-01-01')
    before_2021_mask = scrubbed_df['Time_Load'] < cutoff_date
    before_2021_count = before_2021_mask.sum()
    scrubbed_df = scrubbed_df[~before_2021_mask]

    print(f"  Removed {before_2021_count} records with load times before 2021")

    # Also remove any records where Time_Load is NaT (couldn't be parsed)
    nat_mask = scrubbed_df['Time_Load'].isna()
    nat_count = nat_mask.sum()
    scrubbed_df = scrubbed_df[~nat_mask]

    print(f"  Removed {nat_count} records with invalid/missing load times")

    # Reset index
    scrubbed_df = scrubbed_df.reset_index(drop=True)

    final_count = len(scrubbed_df)
    removed_count = initial_count - final_count

    print(f"\nFiltering complete!")
    print(f"  Original records: {initial_count}")
    print(f"  Filtered records: {final_count}")
    print(f"  Total removed: {removed_count}")

    print("\n=== STEP 2: Matching trucks to haulers ===")

    # Initialize Temp_Hauler_ID column
    scrubbed_df['Temp_Hauler_ID'] = None

    # The truck data has "Carrier" column that contains "CARRIER NAME" format
    # We need to split this to match against hauler data
    matched_count = 0
    unmatched_count = 0

    for idx in range(len(scrubbed_df)):
        truck_carrier_full = str(scrubbed_df.loc[idx, 'Carrier']).strip()

        # Split "CARRIER NAME" format
        parts = truck_carrier_full.split(' ', 1)
        if len(parts) >= 2:
            truck_carrier = parts[0]
            truck_name = parts[1]
        else:
            truck_carrier = truck_carrier_full
            truck_name = ""

        # Get phone if available
        truck_phone = scrubbed_df.loc[idx,
                                      'Phone'] if 'Phone' in scrubbed_df.columns else ""

        # Try to match to a hauler
        hauler_id = match_truck_to_hauler(
            truck_carrier, truck_name, truck_phone, hauler_df)

        if hauler_id is not None:
            scrubbed_df.loc[idx, 'Temp_Hauler_ID'] = hauler_id
            matched_count += 1
        else:
            unmatched_count += 1

        if (idx + 1) % 100 == 0:
            print(f"  Processed {idx + 1}/{len(scrubbed_df)} records...")

    print(f"\nMatching complete!")
    print(f"  Matched to haulers: {matched_count}")
    print(f"  Unmatched: {unmatched_count}")

    # Save to Excel - preserve Master Data Set, only update Scrubbed Data Set
    print(f"\nSaving to {output_file}...")

    try:
        # Load existing workbook to preserve Master Data Set
        book = load_workbook(output_file)

        with pd.ExcelWriter(output_file, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            # Only write/update the Scrubbed Data Set sheet
            scrubbed_df.to_excel(
                writer, sheet_name='Scrubbed Data Set', index=False)

        print("File saved successfully!")

    except FileNotFoundError:
        # If file doesn't exist, create new with both sheets
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            truck_df.to_excel(
                writer, sheet_name='Master Data Set', index=False)
            scrubbed_df.to_excel(
                writer, sheet_name='Scrubbed Data Set', index=False)

        print("File saved successfully!")

    return scrubbed_df


if __name__ == "__main__":
    # Configure your file paths
    truck_file = "c:\\Users\\aschwindt\\OneDrive - The Rasmussen Group, Inc\\Desktop\\Quarry Truck Import.xlsx"
    hauler_file = "c:\\Users\\aschwindt\\OneDrive - The Rasmussen Group, Inc\\Desktop\\Quarry Hualer Import.xlsx"

    # Process the dataset (overwrites Scrubbed Data Set tab only)
    filtered_data = process_quarry_truck_data(
        truck_file=truck_file,
        hauler_file=hauler_file
    )
