import pandas as pd
import re
from pathlib import Path


def normalize_name(name):
    """
    Normalize name by removing special characters, extra spaces, and converting to uppercase.
    Returns empty string for invalid names.
    """
    if pd.isna(name):
        return ""

    # Convert to string and uppercase
    normalized = str(name).strip().upper()

    # Remove common punctuation and special characters
    normalized = re.sub(r'[-_.,:;\'"\\/&()[\]{}]', ' ', normalized)

    # Replace multiple spaces with single space and strip
    normalized = ' '.join(normalized.split())

    return normalized


def is_valid_name(name):
    """
    Check if a name is valid for comparison.
    Returns False for:
    - Empty/null values
    - Pure numbers (e.g., "123", "45678")
    - Generic terms only (pickup, truck, vehicle, etc.)
    """
    if pd.isna(name):
        return False

    name_str = str(name).strip()
    if not name_str or len(name_str) == 0:
        return False

    normalized = normalize_name(name)

    # If empty after normalization
    if not normalized:
        return False

    # Check if it's all numbers
    if normalized.replace(' ', '').isdigit():
        return False

    # Check for generic terms
    generic_terms = {'PICKUP', 'TRUCK', 'VEHICLE', 'CAR', 'VAN', 'TRAILER',
                     'HAULER', 'TRANSPORT', 'DRIVER', 'OPERATOR'}

    words = set(normalized.split())

    # If all words are generic terms, it's not valid
    if words and words.issubset(generic_terms):
        return False

    # Must have at least one letter
    if not any(c.isalpha() for c in normalized):
        return False

    return True


def names_match(name1, name2):
    """
    Check if two names match using multiple methods:
    1. Exact match after normalization
    2. One is substring of another
    3. Same words in different order (e.g., "JON DOE" vs "DOE JON")
    """
    if not name1 or not name2:
        return False

    norm1 = normalize_name(name1)
    norm2 = normalize_name(name2)

    if not norm1 or not norm2:
        return False

    # Exact match
    if norm1 == norm2:
        return True

    # Substring match (one name contains the other)
    if norm1 in norm2 or norm2 in norm1:
        return True

    # Same words, different order
    words1 = sorted(norm1.split())
    words2 = sorted(norm2.split())

    if words1 == words2 and len(words1) > 0:
        return True

    return False


def find_duplicates(df):
    """
    Find duplicate records based on name matching.
    Returns a dictionary mapping duplicate indices to their master record index.
    """
    print("\nFinding duplicates...")

    duplicate_map = {}  # Maps duplicate index -> master index

    # Sort by name for efficient comparison
    df_sorted = df.sort_values('Name').reset_index(drop=True)
    df_sorted['original_index'] = df_sorted.index

    for i in range(len(df_sorted)):
        if i in duplicate_map:
            continue

        current_name = df_sorted.loc[i, 'Name']
        current_carrier = df_sorted.loc[i, 'Carrier']

        # Skip invalid names
        if not is_valid_name(current_name):
            continue

        # Check remaining records
        for j in range(i + 1, len(df_sorted)):
            if j in duplicate_map:
                continue

            compare_name = df_sorted.loc[j, 'Name']
            compare_carrier = df_sorted.loc[j, 'Carrier']

            # Skip invalid names
            if not is_valid_name(compare_name):
                continue

            # Early stopping: if names are too different (first char check)
            norm_current = normalize_name(current_name)
            norm_compare = normalize_name(compare_name)

            if norm_current and norm_compare:
                # If first characters are too far apart in alphabet, stop
                if abs(ord(norm_current[0]) - ord(norm_compare[0])) > 5:
                    break

            # Check if names match using our criteria
            if names_match(current_name, compare_name):
                # Additional check: carriers should be similar
                # (prevent false positives from different companies)
                carrier_match = (
                    pd.isna(current_carrier) and pd.isna(compare_carrier)
                ) or (
                    str(current_carrier).strip().upper() ==
                    str(compare_carrier).strip().upper()
                )

                if carrier_match:
                    duplicate_map[j] = i

        if (i + 1) % 100 == 0:
            print(f"  Processed {i + 1}/{len(df_sorted)} records...")

    print(f"  Found {len(duplicate_map)} duplicates")

    return duplicate_map


def process_hauler_data(input_file):
    """
    Process the Quarry Hauler Import file to create a scrubbed dataset.
    Updates the file in place.

    Args:
        input_file: Path to the Excel file with "Master Data Set" sheet
    """
    print(f"Loading data from: {input_file}")

    # Check if file exists
    if not Path(input_file).exists():
        print(f"Error: File not found: {input_file}")
        return None

    # Check file extension
    file_ext = Path(input_file).suffix.lower()
    print(f"File extension: {file_ext}")

    if file_ext not in ['.xlsx', '.xls']:
        print(
            f"Warning: Unexpected file extension '{file_ext}'. Expected .xlsx or .xls")

    try:
        # Load the master dataset (explicitly specify engine)
        df = pd.read_excel(
            input_file, sheet_name="Master Data Set", engine='openpyxl')
        print(f"Loaded {len(df)} records from Master Data Set")
    except Exception as e:
        print(f"Error reading Excel file: {e}")
        print("\nTrying to diagnose the issue...")

        # Check if it's actually a zip file (xlsx files are zip archives)
        import zipfile
        try:
            with zipfile.ZipFile(input_file, 'r') as zip_ref:
                print(
                    f"File is a valid zip archive with {len(zip_ref.namelist())} files")
        except zipfile.BadZipFile:
            print(
                "Error: File is not a valid zip archive (xlsx files should be zip archives)")
            print("The file may be corrupted or saved in an incompatible format.")
            print("\nSuggestions:")
            print("1. Try opening the file in Excel and re-saving it as .xlsx")
            print("2. Check if the file opens normally in Excel")
            print("3. Ensure the file is not open in another program")

        return None

    # Initialize tracking columns
    df['Duplicate_Carriers'] = ""
    df['Duplicate_Names'] = ""
    df['Is_Duplicate'] = False

    # Find duplicates
    duplicate_map = find_duplicates(df)

    # Mark duplicates and build the duplicate lists
    for dup_idx, master_idx in duplicate_map.items():
        # Mark as duplicate
        df.loc[dup_idx, 'Is_Duplicate'] = True

        # Add to master's duplicate lists
        dup_carrier = str(df.loc[dup_idx, 'Carrier']).strip()
        dup_name = str(df.loc[dup_idx, 'Name']).strip()

        # Update Duplicate_Carriers
        current_carriers = str(df.loc[master_idx, 'Duplicate_Carriers'])
        if current_carriers and current_carriers != 'nan' and current_carriers != '':
            df.loc[master_idx,
                   'Duplicate_Carriers'] = f"{current_carriers}; {dup_carrier}"
        else:
            df.loc[master_idx, 'Duplicate_Carriers'] = dup_carrier

        # Update Duplicate_Names
        current_names = str(df.loc[master_idx, 'Duplicate_Names'])
        if current_names and current_names != 'nan' and current_names != '':
            df.loc[master_idx,
                   'Duplicate_Names'] = f"{current_names}; {dup_name}"
        else:
            df.loc[master_idx, 'Duplicate_Names'] = dup_name

    # Create scrubbed dataset (non-duplicates only)
    scrubbed_df = df[~df['Is_Duplicate']].copy()
    scrubbed_df = scrubbed_df.drop(columns=['Is_Duplicate'])
    scrubbed_df = scrubbed_df.reset_index(drop=True)

    # Sort by carrier for final output
    scrubbed_df = scrubbed_df.sort_values('Carrier').reset_index(drop=True)

    print(f"\nResults:")
    print(f"  Original records: {len(df)}")
    print(f"  Unique records: {len(scrubbed_df)}")
    print(f"  Duplicates removed: {len(df) - len(scrubbed_df)}")

    # Save to the input file (update in place)
    print(f"\nUpdating file: {input_file}")

    # Use openpyxl to load existing workbook and update it
    from openpyxl import load_workbook
    from openpyxl.utils.dataframe import dataframe_to_rows

    try:
        # Load the existing workbook
        book = load_workbook(input_file)

        # Remove the Scrubbed Data Set sheet if it exists
        if 'Scrubbed Data Set' in book.sheetnames:
            del book['Scrubbed Data Set']

        # Create new Scrubbed Data Set sheet
        ws = book.create_sheet('Scrubbed Data Set')

        # Write the scrubbed dataframe to the sheet
        for r_idx, row in enumerate(dataframe_to_rows(scrubbed_df, index=False, header=True), 1):
            for c_idx, value in enumerate(row, 1):
                ws.cell(row=r_idx, column=c_idx, value=value)

        # Save the workbook
        book.save(input_file)
        book.close()

        print("Processing complete!")

    except Exception as e:
        print(f"Error updating file: {e}")
        # Fallback: create a new file with both sheets
        with pd.ExcelWriter(input_file, engine='openpyxl', mode='w') as writer:
            df_master = pd.read_excel(input_file, sheet_name="Master Data Set")
            df_master.to_excel(
                writer, sheet_name='Master Data Set', index=False)
            scrubbed_df.to_excel(
                writer, sheet_name='Scrubbed Data Set', index=False)

    return scrubbed_df


if __name__ == "__main__":
    # Configure your file path
    input_file = "c:\\Users\\aschwindt\\OneDrive - The Rasmussen Group, Inc\\Desktop\\Quarry Hualer Import.xlsx"

    # Process the data (updates the file in place)
    scrubbed_data = process_hauler_data(input_file)

    print(f"\nFile updated successfully!")
