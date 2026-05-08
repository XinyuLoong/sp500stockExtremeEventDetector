from datetime import date
import pandas as pd
import argparse

DATAHUB_ENDPOINT = (
    "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/master/data/constituents.csv"
)

def get_sp500_constituents(output_file: str = "stocklist.csv") -> None:

    """
    Get the current S&P 500 constituent list from DataHub/GitHub and save it as .csv
    The .csv file will be the input for main.py
    """

    # Get data from public CSV, store original data in var: raw_df
    raw_df = pd.read_csv(DATAHUB_ENDPOINT)
    if raw_df.empty:
        raise RuntimeError("Data source returned an empty list.")

    # Change name
    column_mapping = {
        "Symbol": "symbol",
        "Security": "company_name",
        "GICS Sector": "sector",
        "GICS Sub-Industry": "sub_sector",
        "Headquarters Location": "headquarters",
        "Date added": "date_first_added",
        "CIK": "cik",
        "Founded": "founded",
    }
    available_columns = {old: new for old, new in column_mapping.items() if old in raw_df.columns}
    df = raw_df[list(available_columns.keys())].rename(columns=available_columns)
    
    # Check the requried cols are here
    required_columns = ["symbol", "company_name"]
    for col in required_columns:
        if col not in df.columns:
            raise RuntimeError(f"Required column missing from data source: {col}")

    # Adjust the format of the table
    df["last_updated"] = date.today().isoformat()
    order = [
        "symbol",
        "company_name",
        "sector",
        "sub_sector",
        "headquarters",
        "date_first_added",
        "cik",
        "founded",
        "last_updated",
    ]
    ordered_columns = [col for col in order if col in df.columns]
    df = df[ordered_columns]
    df = df.sort_values("symbol").reset_index(drop=True)
    df.to_csv(output_file, index=False)
    print(f"Saved {len(df)} S&P 500 constituents to {output_file}")

# For command line execution
def parse_args():
    parser = argparse.ArgumentParser(
        description="Harvest the current S&P 500 constituent list from DataHub/GitHub."
    )
    parser.add_argument(
        "--output-file",
        default ="stocklist.csv",
        help = "Output CSV file name. Default: stocklist.csv",
    )

    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    get_sp500_constituents(
        output_file = args.output_file,
    )