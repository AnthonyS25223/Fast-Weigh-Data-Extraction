import pandas as pd
from fuzzywuzzy import fuzz
import numpy as np


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


def is_generic_name(name):
    """
    Check if a name is too generic to be used for matching.
    Returns True if the name is generic (like 'pick up', numbers, etc.)
    """
    if not name or len(name.strip()) == 0:
        return True

    normalized = normalize_name(name)

    # Check if it's just numbers
    if normalized.replace(' ', '').isdigit():
        return True

    # List of generic terms that shouldn't trigger matches
    generic_terms = [
        'PICK UP', 'PICKUP', 'DELIVERY', 'DRIVER', 'TRUCK', 'HAULER',
        'UNKNOWN', 'N/A', 'NA', 'NONE', 'TBD', 'TEST', 'TEMP'
    ]

    # Check if the entire name is just a generic term
    if normalized in generic_terms:
        return True

    # Check if name is very short (likely not a real business name)
    if len(normalized) <= 2:
        return True

    return False


def is_substring_match(name1, name2):
    """
    Check if one name is fully contained within the other.
    E.g., "JOHN DOE CONSTRUCTION" contains "JOHN DOE CONSTRUCTION LLC"
    Returns True if one is a substring of the other (after normalization).
    """
    n1 = normalize_name(name1)
    n2 = normalize_name(name2)

    # Skip if either name is generic
    if is_generic_name(n1) or is_generic_name(n2):
        return False

    # Remove common business suffixes for comparison
    suffixes = ['LLC', 'INC', 'CORP', 'LTD', 'CO', 'COMPANY', 'INCORPORATED',
                'LIMITED', 'CORPORATION']

    n1_words = n1.split()
    n2_words = n2.split()

    # Remove suffix words from both
    n1_core = ' '.join([w for w in n1_words if w not in suffixes])
    n2_core = ' '.join([w for w in n2_words if w not in suffixes])

    # Check if one core name is contained in the other
    # Both directions to catch cases like "JOHN DOE" in "JOHN DOE CONSTRUCTION"
    if len(n1_core) > 0 and len(n2_core) > 0:
        if n1_core in n2_core or n2_core in n1_core:
            # Make sure the match is substantial (not just "A" in "ABC")
            shorter = min(len(n1_core), len(n2_core))
            if shorter >= 5:  # Require at least 5 characters for substring match
                return True

    return False


def is_exact_name_match(name1, name2):
    """
    Check if names are exactly the same after normalization.
    Returns True only if names match and aren't generic.
    """
    n1 = normalize_name(name1)
    n2 = normalize_name(name2)

    # Skip if either name is generic
    if is_generic_name(n1) or is_generic_name(n2):
        return False

    return n1 == n2


def run_deduplication_pass(df, min_comparison_threshold, sort_by='Name', existing_duplicates=None):
    """
    Run a deduplication pass on the dataframe.

    Args:
        df: DataFrame to process
        min_comparison_threshold: Minimum similarity to continue comparing
        sort_by: Field to use for comparison ('Name' or 'Carrier')
        existing_duplicates: Dictionary of already-found duplicates to preserve

    Returns:
        Updated duplicate_map dictionary
    """
    if existing_duplicates is None:
        duplicate_map = {}
    else:
        duplicate_map = existing_duplicates.copy()

    comparison_field = sort_by

    for i in range(len(df)):
        if i in duplicate_map:
            # Already marked as duplicate
            continue

        current_name = df.loc[i, 'Name']
        current_phone = df.loc[i, 'Phone']
        current_carrier = df.loc[i, 'Carrier']
        current_compare_value = df.loc[i, comparison_field]

        # Check remaining records for duplicates with early stopping
        for j in range(i + 1, len(df)):
            if j in duplicate_map:
                continue

            compare_name = df.loc[j, 'Name']
            compare_phone = df.loc[j, 'Phone']
            compare_carrier = df.loc[j, 'Carrier']
            compare_compare_value = df.loc[j, comparison_field]

            # Early stopping: if comparison field values are too dissimilar, stop comparing
            if sort_by == 'Name':
                similarity = fuzz.ratio(normalize_name(
                    current_compare_value), normalize_name(compare_compare_value))
            else:  # Carrier
                similarity = fuzz.ratio(str(current_compare_value).upper(), str(
                    compare_compare_value).upper())

            if similarity < min_comparison_threshold:
                # Values are sorted, so if this value is too different,
                # all following values will be even more different
                break

            # Check for matches
            carriers_match = str(current_carrier).strip(
            ).upper() == str(compare_carrier).strip().upper()

            # Check if names are the same words in different order (e.g., "MIKE YOUNG" vs "YOUNG MIKE")
            current_words = sorted(normalize_name(current_name).split())
            compare_words = sorted(normalize_name(compare_name).split())
            words_match = current_words == compare_words and len(
                current_words) > 0 and carriers_match

            # NEW: Check for exact name match (after normalization, non-generic)
            exact_name = is_exact_name_match(
                current_name, compare_name) and carriers_match

            # NEW: Check for substring match (one name contained in the other)
            substring = is_substring_match(
                current_name, compare_name) and carriers_match

            # Existing soft match (name similarity + phone match)
            soft_match = is_soft_match(current_name, compare_name,
                                       current_phone, compare_phone) and carriers_match

            # Mark as duplicate if ANY of these conditions are met
            if exact_name or substring or soft_match or words_match:
                # Mark j as duplicate of i
                duplicate_map[j] = i
                df.loc[j, 'Is_Duplicate'] = True

                # Add the duplicate's info to the kept record (i)
                current_dup_carrier = str(df.loc[i, 'Duplicate_Of_Carrier'])
                current_dup_name = str(df.loc[i, 'Duplicate_Of_Name'])

                if current_dup_carrier == "" or current_dup_carrier == "nan":
                    df.loc[i, 'Duplicate_Of_Carrier'] = str(compare_carrier)
                    df.loc[i, 'Duplicate_Of_Name'] = str(compare_name)
                else:
                    df.loc[i, 'Duplicate_Of_Carrier'] = current_dup_carrier + \
                        f"; {compare_carrier}"
                    df.loc[i, 'Duplicate_Of_Name'] = current_dup_name + \
                        f"; {compare_name}"

        if (i + 1) % 100 == 0:
            print(f"  Processed {i + 1}/{len(df)} records...")

    return duplicate_map


def add_load_times(scrubbed_df, quarry_truck_file, quarry_sheet_name="Sheet1"):
    """
    Add most recent load time from Quarry Truck imports.

    Args:
        scrubbed_df: The scrubbed dataset DataFrame
        quarry_truck_file: Path to the Quarry Truck imports Excel file
        quarry_sheet_name: Sheet name in the Quarry Truck file (default: "Sheet1")

    Returns:
        DataFrame with Load_Time column added
    """
    print(f"\nLoading Quarry Truck data from {quarry_truck_file}...")

    try:
        quarry_df = pd.read_excel(
            quarry_truck_file, sheet_name=quarry_sheet_name)
        print(f"  Loaded {len(quarry_df)} records from Quarry Truck imports")

        # Ensure Time Load column exists
        if 'Time_Load' not in quarry_df.columns:
            print("  Warning: 'Time_Load' column not found in Quarry Truck file")
            scrubbed_df['Load_Time'] = ""
            return scrubbed_df

        # First, replace the invalid "00:00:00 00:00:00" format with a recognizable default
        quarry_df['Time_Load'] = quarry_df['Time_Load'].replace(
            '00:00:00 00:00:00', '1900-01-01 00:00:00')

        # Convert Time Load to datetime for comparison
        quarry_df['Time_Load'] = pd.to_datetime(
            quarry_df['Time_Load'], errors='coerce')

        # Initialize Load_Time column
        scrubbed_df['Load_Time'] = ""

        print("  PASS 1: Exact matching (Carrier + Name)...")

        # PASS 1: Exact match - For each record in scrubbed dataset
        for idx in range(len(scrubbed_df)):
            carrier = scrubbed_df.loc[idx, 'Carrier']
            name = scrubbed_df.loc[idx, 'Name']

            # Create the search key: "Carrier Name"
            search_key = f"{carrier} {name}".strip()

            # Find matching records in quarry data
            matches = quarry_df[quarry_df['Carrier'].astype(
                str).str.strip() == search_key]

            if len(matches) > 0:
                # Get the most recent Time Load
                most_recent = matches['Time_Load'].max()

                if pd.notna(most_recent):
                    # Check if it's the default system date (1900-01-01 00:00:00)
                    if most_recent == pd.Timestamp('1900-01-01 00:00:00'):
                        scrubbed_df.loc[idx,
                                        'Load_Time'] = "No Load Time (Default: 1/1/1900)"
                    else:
                        scrubbed_df.loc[idx, 'Load_Time'] = most_recent

            if (idx + 1) % 100 == 0:
                print(f"    Processed {idx + 1}/{len(scrubbed_df)} records...")

        # Final summary
        records_with_times_final = scrubbed_df['Load_Time'].astype(
            str).str.strip().ne("").sum()
        print(
            f"\n  TOTAL: Found load times for {records_with_times_final}/{len(scrubbed_df)} records")

    except FileNotFoundError:
        print(f"  Error: File not found: {quarry_truck_file}")
        scrubbed_df['Load_Time'] = ""
    except Exception as e:
        print(f"  Error loading Quarry Truck data: {e}")
        scrubbed_df['Load_Time'] = ""

    return scrubbed_df


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

    # Check if names are the same words but in different order (e.g., "MIKE YOUNG" vs "YOUNG MIKE")
    words1 = sorted(n1.split())
    words2 = sorted(n2.split())
    words_match = words1 == words2 and len(words1) > 0

    # Strong soft match: similar names AND matching phones
    phones_match = p1 == p2 and p1 != ""
    names_similar = name_score >= name_threshold or words_match

    return names_similar and phones_match


def process_master_dataset(input_file, quarry_truck_file=None, quarry_sheet_name="Sheet1", output_file=None):
    """
    Process master dataset to create scrubbed dataset with deduplication.

    Args:
        input_file: Path to Excel file with "Master Data Set" tab
        quarry_truck_file: Path to Quarry Truck imports Excel file (optional)
        quarry_sheet_name: Sheet name in Quarry Truck file (default: "Sheet1")
        output_file: Path to save the processed Excel file (if None, overwrites input_file)
    """

    if output_file is None:
        output_file = input_file

    print("Loading Master Data Set...")
    df = pd.read_excel(input_file, sheet_name="Master Data Set")

    print(f"Total records in Master Data Set: {len(df)}")

    # Initialize columns for the scrubbed dataset
    df['Temp_Hauler_ID'] = range(1, len(df) + 1)
    df['Duplicate_Of_Carrier'] = ""
    df['Duplicate_Of_Name'] = ""
    df['Is_Duplicate'] = False

    # Ensure these columns are string type to avoid float issues
    df['Duplicate_Of_Carrier'] = df['Duplicate_Of_Carrier'].astype(
        str).replace('nan', '')
    df['Duplicate_Of_Name'] = df['Duplicate_Of_Name'].astype(
        str).replace('nan', '')

    # Track which records to keep
    duplicate_map = {}  # Maps duplicate index to the master record index

    # Sort by Name for efficient comparison
    print("\nSorting data by name for efficient processing...")
    df = df.sort_values('Name').reset_index(drop=True)

    # Minimum similarity threshold to continue comparing (50% means very different)
    min_comparison_threshold = 80

    print("Processing deduplication - PASS 1: Sorting by Name...")

    duplicate_map = run_deduplication_pass(
        df, min_comparison_threshold, sort_by='Name')

    # Now do a second pass sorting by Carrier
    print("\nProcessing deduplication - PASS 2: Sorting by Carrier...")
    df = df.sort_values('Carrier').reset_index(drop=True)

    duplicate_map = run_deduplication_pass(
        df, min_comparison_threshold, sort_by='Carrier', existing_duplicates=duplicate_map)

    # Create scrubbed dataset (unique records only)
    scrubbed_df = df[~df['Is_Duplicate']].copy()
    scrubbed_df = scrubbed_df.reset_index(drop=True)

    # Reassign Temp_Hauler_ID for scrubbed dataset
    scrubbed_df['Temp_Hauler_ID'] = range(1, len(scrubbed_df) + 1)

    # Sort final output by Carrier
    scrubbed_df = scrubbed_df.sort_values('Carrier').reset_index(drop=True)

    # Add load times from Quarry Truck imports if file provided
    if quarry_truck_file:
        scrubbed_df = add_load_times(
            scrubbed_df, quarry_truck_file, quarry_sheet_name)

    print(f"\nDeduplication complete!")
    print(f"  Original records: {len(df)}")
    print(f"  Unique records: {len(scrubbed_df)}")
    print(f"  Duplicates removed: {len(df) - len(scrubbed_df)}")

    # Save to Excel - preserve Master Data Set, only update Scrubbed Data Set
    print(f"\nSaving to {output_file}...")

    # Load existing workbook to preserve Master Data Set
    from openpyxl import load_workbook

    try:
        book = load_workbook(output_file)

        with pd.ExcelWriter(output_file, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            # Only write/update the Scrubbed Data Set sheet
            scrubbed_df.to_excel(
                writer, sheet_name='Scrubbed Data Set', index=False)
    except FileNotFoundError:
        # If file doesn't exist, create new with both sheets
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Master Data Set', index=False)
            scrubbed_df.to_excel(
                writer, sheet_name='Scrubbed Data Set', index=False)

    print("File saved successfully!")

    return scrubbed_df


if __name__ == "__main__":
    # Configure your file paths
    input_file = "c:\\Users\\aschwindt\\OneDrive - The Rasmussen Group, Inc\\Desktop\\Quarry Hualer Import.xlsx"
    # Path to Quarry Truck data
    quarry_truck_file = "c:\\Users\\aschwindt\\OneDrive - The Rasmussen Group, Inc\\Desktop\\Quarry Truck Import.xlsx"
    quarry_sheet_name = "Master Data Set"  # Sheet name in Quarry Truck file

    # Process the dataset (overwrites Scrubbed Data Set tab only)
    scrubbed_data = process_master_dataset(
        input_file=input_file,
        quarry_truck_file=quarry_truck_file,
        quarry_sheet_name=quarry_sheet_name
    )
