import pandas as pd
import os
from pathlib import Path


def concatenate_datasets(input_files, output_folder="reports", output_filename="Quarry Hualer Import.xlsx", sheet_name=None):
    """
    Concatenate multiple Excel or CSV datasets and save to reports folder.

    Args:
        input_files: List of file paths to concatenate
        output_folder: Folder to save the output (default: "reports")
        output_filename: Name of the output file (default: "Quarry Hualer Import.xlsx")
        sheet_name: For Excel files, specify which sheet to read (default: first sheet)
    """

    # Create reports folder if it doesn't exist
    Path(output_folder).mkdir(parents=True, exist_ok=True)

    # Read all datasets
    dataframes = []
    for file in input_files:
        try:
            # Determine file type and read accordingly
            if file.endswith(('.xlsx', '.xls')):
                df = pd.read_excel(file, sheet_name=sheet_name or 0)
            elif file.endswith('.csv'):
                df = pd.read_csv(file)
            else:
                print(f"Skipping unsupported file: {file}")
                continue

            dataframes.append(df)
            print(f"Loaded: {file} ({len(df)} rows)")
        except Exception as e:
            print(f"Error loading {file}: {e}")

    # Concatenate all dataframes
    if dataframes:
        combined_df = pd.concat(dataframes, ignore_index=True)

        # Save to reports folder
        output_path = os.path.join(output_folder, output_filename)

        # Save based on output file extension
        if output_filename.endswith(('.xlsx', '.xls')):
            combined_df.to_excel(output_path, index=False, engine='openpyxl')
        else:
            combined_df.to_csv(output_path, index=False)

        print(f"\nSuccessfully concatenated {len(dataframes)} files")
        print(f"Total rows: {len(combined_df)}")
        print(f"Output saved to: {output_path}")
    else:
        print("No files were successfully loaded.")


if __name__ == "__main__":
    files_to_concat = [
        "c:\\Users\\aschwindt\\OneDrive - The Rasmussen Group, Inc\\Desktop\\JWS Reports\\Coppock - Quarry Truck Import Report.xlsx",
        "c:\\Users\\aschwindt\\OneDrive - The Rasmussen Group, Inc\\Desktop\\JWS Reports\\Fort Madison - Quarry Truck Import Report.xlsx",
        "c:\\Users\\aschwindt\\OneDrive - The Rasmussen Group, Inc\\Desktop\\JWS Reports\\Kahoka - Quarry Truck Import Report.xlsx",
        "c:\\Users\\aschwindt\\OneDrive - The Rasmussen Group, Inc\\Desktop\\JWS Reports\\Mediapolis - Quarry Truck Import Report.xlsx",
        "c:\\Users\\aschwindt\\OneDrive - The Rasmussen Group, Inc\\Desktop\\JWS Reports\\Wayland - Quarry Truck Import Report.xlsx"
    ]

    concatenate_datasets(
        files_to_concat, output_filename="Quarry Truck Import.xlsx")
