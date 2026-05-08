from datetime import date
import pandas as pd
import argparse
from io import StringIO
import requests

WIKIPEDIA_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

def get_sp500_constituents(output_file: str = "stocklist.csv") -> None:

    """
    Get the current S&P 500 constituent list from Wikipedia and save it as .csv
    The .csv file will be the input for main.py
    """

    # Get data from Wikipedia table, store original data in var: raw_df
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(WIKIPEDIA_URL, headers=headers, timeout=30)
    response.raise_for_status()
    tables = pd.read_html(StringIO(response.text))
    if not tables:
        raise RuntimeError("Wikipedia returned no tables.")
    raw_df = tables[0]
    if raw_df.empty:
        raise RuntimeError("Wikipedia returned an empty list.")

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
            raise RuntimeError(f"Required column missing from Wikipedia table: {col}")

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
        description = "Harvest the current S&P 500 constituent list from Wikipedia."
    )
    parser.add_argument(
        "--output-file",
        default = "stocklist.csv",
        help = "Output CSV file name. Default: stocklist.csv",
    )
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    get_sp500_constituents(
        output_file = args.output_file,
    )