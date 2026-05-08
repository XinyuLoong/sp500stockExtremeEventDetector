from datetime import date
import pandas as pd
import requests
import argparse

FMP_ENDPOINT = "https://financialmodelingprep.com/stable/sp500-constituent"

def get_sp500_constituents(api_key: str, output_file: str = "stocklist.csv") -> None:

    """
    Get the current S&P 500 constituent list from Financial Modeling Prep and save it as .csv
    The .csv file will be the input for main.py
    """

    # Get data from API, store original data in var: raw_df
    if not api_key:
        raise RuntimeError(
            "Missing API key. Please provide it with --api-key."
        )
    response = requests.get(
        FMP_ENDPOINT,
        params = {"apikey": api_key},
        timeout = 30,
    )
    response.raise_for_status()
    
    data = response.json()
    if not data:
        raise RuntimeError("API returned an empty list.")
    raw_df = pd.DataFrame(data)

    # Change name
    column_mapping = {
        "symbol": "symbol",
        "name": "company_name",
        "sector": "sector",
        "subSector": "sub_sector",
        "headQuarter": "headquarters",
        "dateFirstAdded": "date_first_added",
        "cik": "cik",
        "founded": "founded",
    }
    available_columns = {old: new for old, new in column_mapping.items() if old in raw_df.columns}
    df = raw_df[list(available_columns.keys())].rename(columns=available_columns)
    
    # Check the requried cols are here
    required_columns = ["symbol", "company_name"]
    for col in required_columns:
        if col not in df.columns:
            raise RuntimeError(f"Required column missing from API response: {col}")

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
        description="Harvest the current S&P 500 constituent list from Financial Modeling Prep."
    )
    parser.add_argument(
        "--api-key",
        required = True,
        help = "Financial Modeling Prep API key.",
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
        api_key = args.api_key,
        output_file = args.output_file,
    )


