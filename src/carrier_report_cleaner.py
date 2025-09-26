import pandas as pd
import os


def clean_carrier_report(file_path: str, output_path: str = None) -> pd.DataFrame:
    """
    Clean up a carrier report by extracting specific columns and removing empty rows.

    Structure:
    - Skip first 3 rows (headers)
    - Skip columns A and B (not used)  
    - Extract: Carrier (C), Name (D), Phone (K), Contact Name (M)
    - Remove empty rows
    - Shift columns to A, B, C, D positions

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

    # Process each row starting from row 4 (index 3)
    for idx, row in df_raw.iterrows():
        if idx < 3:  # Skip first 3 rows
            continue

        row_list = row.tolist()

        # Extract the specific columns we need
        carrier = str(row_list[2]).strip() if len(
            row_list) > 2 else ''      # Column C
        name = str(row_list[3]).strip() if len(
            row_list) > 3 else ''         # Column D
        phone = str(row_list[10]).strip() if len(
            row_list) > 10 else ''      # Column K
        contact = str(row_list[12]).strip() if len(
            row_list) > 12 else ''    # Column M

        # Skip completely empty rows
        if not carrier and not name and not phone and not contact:
            continue

        # Skip header rows
        if carrier.lower() == 'carrier' or name.lower() == 'name':
            continue

        # Create record
        record = {
            'Carrier': carrier,
            'Name': name,
            'Phone': phone,
            'Contact_Name': contact
        }

        cleaned_data.append(record)

    # Create DataFrame
    result_df = pd.DataFrame(cleaned_data)

    # Clean up the data
    result_df = clean_data_types(result_df)

    # Remove rows where all fields are empty
    result_df = result_df.dropna(how='all')

    # Remove rows where all fields are just 'nan' strings
    result_df = result_df[~((result_df == '') | (
        result_df == 'nan')).all(axis=1)]

    # Save to file if output path provided
    if output_path and not result_df.empty:
        result_df.to_excel(output_path, index=False)

    return result_df


def clean_data_types(df: pd.DataFrame) -> pd.DataFrame:
    """Clean up data types and remove unwanted values."""
    if df.empty:
        return df

    # Clean up all text columns
    for col in df.columns:
        df[col] = df[col].astype(str).str.strip()
        df[col] = df[col].replace('nan', '')
        df[col] = df[col].replace('NaN', '')
        df[col] = df[col].replace('', None)

    return df


# Run Script
if __name__ == "__main__":

    # Set up paths
    input_file = "c:\\Users\\aschwindt\\Downloads\\Carrier Report.xls"
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Navigate to the reports folder relative to the script location
    reports_dir = os.path.join(script_dir, "..", "reports")
    output_file = os.path.join(reports_dir, "Carrier_Report_Processed.xlsx")

    # Create reports directory if it doesn't exist
    os.makedirs("../reports", exist_ok=True)

    cleaned_df = clean_carrier_report(input_file, output_file)

    # Show Total Carriers for comparison with original file
    print(f"Total carriers: {len(cleaned_df)}")
