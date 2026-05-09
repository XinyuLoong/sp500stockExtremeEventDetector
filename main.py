import pandas as pd
import numpy as np
import argparse
from datetime import datetime, time, timezone
import pandas_market_calendars as mcal
import yfinance as yf

from notifier import send_notifications # Sending nitification API

#-----------------------------------------------------------------------------
#            Helpers functions for main.py
#-----------------------------------------------------------------------------
def parse_args():

    '''
    Parse command line arguments for main.py
    users can change the variables when executing main.py:
    @ params[in]:
    --days: number of recent calendar days used to calculate high and low prices. Default: 10
    --threshold: price movement threshold. Eg: 0.10 means 10%. Default
    --stock-file: input .csv file containing the stock list. Default: stocklist.csv
    --state-file: output .csv file storing current stock extremes. Default: stock_extremes.csv
    @ return: parsed arguments
    '''

    parser = argparse.ArgumentParser(description = "Monitor S&P 500 stock price movements.")
    parser.add_argument("--days", type = int, default = 10, help = "Number of recent calendar days used to calculate high and low prices.")
    parser.add_argument("--threshold", type = float, default=0.10, help = "Price movement threshold. Eg: 0.10 means 10%.")
    parser.add_argument("--stock-file", default = "stocklist.csv", help = "Input .csv file containing the stock list.")
    parser.add_argument("--state-file", default = "stock_extremes.csv", help = "Output .csv file storing current stock extremes.")
    # Add this option for testing (When we want to test the program outside trading hours)
    parser.add_argument("--force-run", action = "store_true", help = "Force the program to run even outside trading hours. Useful for testing.")
    return parser.parse_args()


def symbol_to_name_map(stock_df: pd.DataFrame):
    """
    Build a dictionary that maps stock symbols to company names.
    Used for merging the stock price events with company names for better notification messages.

    @ params[in]:
        stock_df: A DataFrame loaded from stocklist.csv.
    @ return:
        dict: {symbol: company_name}
    """

    if "company_name" not in stock_df.columns:
        return {}
    symbol_to_name = (stock_df[["symbol", "company_name"]]
                      .dropna(subset=["symbol"])
                      .set_index("symbol")["company_name"]
                      .to_dict()
    )
    return symbol_to_name


def is_market_open_now():

    '''
    Check if the US stock market is open at the current moment, considering both time and holidays.
    Assumpetion: US stock market regular hours = 9:30 AM - 4:00 PM Eastern Time
    @ params[in]: None
    @ return: True if market is open, False otherwise
    '''

    nyse = mcal.get_calendar("NYSE") # Get the NYSE calendar
    now_utc = datetime.now(timezone.utc) # Get current time in UTC

    # schedule would be a DataFrame with columns: market_open, market_close, and rows for each trading day in the specified date range
    schedule = nyse.schedule(start_date = now_utc.date(), end_date = now_utc.date()) # Look up the market schedule for today

    # Check 1: is today a trading day?
    if schedule.empty:
        return False
    
    # Check 2: is current time within market hours?
    market_open = schedule.iloc[0]["market_open"]
    market_close = schedule.iloc[0]["market_close"]

    return market_open <= now_utc <= market_close


def poll_prices(symbols: list[str], days: int):

    '''
    Poll the current price, recent max and min prices for a list of stocks.
    Use yfinance API: https://pypi.org/project/yfinance/
    Use yfinance.download(tickers, period="Xd", interval="5m") to get historical price data for the range of days, and we can also spesifiy the interval of the data (eg: 5m means we get 5-minute price data).
    @ params[in]:
        symbols: A list of stock symbols to poll.
        days: Number of recent calendar days used to calculate max and min prices.
    @ return: A DataFrame with columns: symbol, current_price, window_max, window_min
    '''

    rows = []
    # Since yahoo Finance symbol is different from Wikipedia for some stocks (eg: BRK.B in Wikipedia is BRK-B in Yahoo Finance)
    # we need to adjust the symbols, and adjust them back after polling prices
    symbol_map = {symbol: symbol.replace(".", "-") for symbol in symbols}
    yahoo_symbols = list(symbol_map.values())

    # Get historical intraday price data
    period = f"{days}d"
    try:
        data = yf.download(tickers = yahoo_symbols,
                           period = period, # number of recent calendar days used to calculate max and min prices
                           interval = "5m", # the interval of the data, we can get 5-minute price data
                           group_by = "ticker", # group the data by ticker, so that we can easily get the price data for each stock
                           auto_adjust = False, # only get the raw price data without any adjustment
                           prepost = False, # only get the regular trading hours data, no pre-market or after-hours data
                           progress = True, # progress bar when downloading data
                           threads = True, # use multi-threading to speed up the downloading
                           )
    except Exception as e:
        print(f"Error downloading data from Yahoo Finance: {e}")
        raise RuntimeError("Failed to download price data from Yahoo Finance.")

    # debug test
    # pd.DataFrame(data).to_csv("price_data_for_debugging.csv", index=True)

    for original_symbol, yahoo_symbol in symbol_map.items():
        try:
            if isinstance(data.columns, pd.MultiIndex):
                # if multiple columns, and we group by ticker, columns would be a MultiIndex with levels: [symbol, price attribute]
                if yahoo_symbol not in data.columns.get_level_values(0):
                    print(f"Warning: No price data found for {original_symbol}. Skip.")
                    continue
                # get the price data for this symbol
                symbol_data = data.xs(yahoo_symbol, level=0, axis=1)
            else:
                symbol_data = data.copy()
            symbol_data = symbol_data.dropna(subset=["Close", "High", "Low"])

            # If there is no price data for this symbol, skip it
            if len(symbol_data) < 2:
                print(f"Price data for {original_symbol} is empty. Skip.")
                continue

            current_price = float(symbol_data["Close"].iloc[-1])
            history_data = symbol_data.iloc[:-1]
            window_max = float(history_data["High"].max())
            window_min = float(history_data["Low"].min())
            rows.append({"symbol": original_symbol,
                         "current_price": current_price,
                         "window_max": window_max,
                         "window_min": window_min})
        except Exception as e:
            print(f"Warning: Failed to process {original_symbol}: {e}")
    
    output_table = pd.DataFrame(rows)

    # Save the price data to a .csv file for debugging
    # output_table.to_csv("price_data_for_debugging.csv", index=False)

    return output_table


def detect_events(price_df: pd.DataFrame, threshold: float, symbol_to_name: dict):

    """
    Detect stock price reluctance events.
    DROP: Current price is more than threshold below the recent minimum.
          drop_pct = (current_price - window_min) / window_min
    RISE: Current price is more than threshold above the recent maximum.
          rise_pct = (current_price - window_max) / window_max
    @ params[in]:
        price_df: A DataFrame containing columns: symbol, current_price, window_max, window_min
        threshold: Price movement threshold. Eg: 0.10 means 10%.
    @ return: list[dict] - A list of event dictionaries. Each dictionary contains:
        - symbol
        - event_type ("DROP" / "RISE")
        - current_price
        - reference_price (the recent min for DROP, recent max for RISE)
        - change_pct (the percentage change from the reference price to the current price)
        - message (a string message describing the event)
    """
    events = []

    for _, row in price_df.iterrows():
        symbol = row["symbol"]
        current_price = row["current_price"]
        window_max = row["window_max"]
        window_min = row["window_min"]

        drop_pct = (current_price - window_min) / window_min # negative value if dropped
        rise_pct = (current_price - window_max) / window_max # positive value if rose

        # Only consider it an event if the price movement exceeds the threshold
        # 1. DROP event: current price dropped more than threshold from recent max
        # 2. RISE event: current price rose more than threshold from recent min
        if drop_pct < -threshold:
            events.append({
                "symbol": symbol,
                "company_name": symbol_to_name.get(symbol, ""),
                "event_type": "DROP",
                "current_price": current_price,
                "reference_price": window_min,
                "change_pct": drop_pct,
                "message": (f"{symbol} dropped {drop_pct:.2%} from its {window_min:.2f} days recent minimum price.")
            })

        if rise_pct > threshold:
            events.append({
                "symbol": symbol,
                "company_name": symbol_to_name.get(symbol, ""),
                "event_type": "RISE",
                "current_price": current_price,
                "reference_price": window_max,
                "change_pct": rise_pct,
                "message": (f"{symbol} rose {rise_pct:.2%} from its {window_max:.2f} days recent maximum price.")
            })

    return events


def build_state_table(price_df: pd.DataFrame, events: list[dict], symbol_to_name: dict):
    """
    Build the state table for all monitored stocks and extreme events.
    @ params[in]:
        price_df: A DataFrame containing columns: symbol, current_price, window_max, window_min (created by poll_prices() function)
        events: A list of event dictionaries. Each dictionary contains:
            - symbol
            - event_type ("DROP" / "RISE")
            - current_price
            - reference_price (the recent min for DROP, recent max for RISE)
            - change_pct (the percentage change from the reference price to the current price)
            - message (a string message describing the event)
        stock_df: A DataFrame containing stock information (created by get_stock.py), used for mergeing to get company names
    @ return: A DataFrame containing the current state of all monitored stocks, including any detected events.
        The DataFrame will have columns:
            - symbol
            - current_price
            - window_max
            - window_min
            - drop_pct
            - rise_pct
            - latest_event (the most recent event type for this stock, or "NONE" if no event)
            - check_time (timestamp of the last price check)
    """

    # Change a list of event dicts into a map of symbol 
    event_map = {}
    for event in events:
        symbol = event["symbol"]
        event_map[symbol] = event["event_type"]

    # Build the state DataFrame by merging price_df with the latest event info
    state_rows = []
    for _, row in price_df.iterrows():
        symbol = row["symbol"]
        company_name = symbol_to_name.get(symbol, "")
        current_price = row["current_price"]
        window_max = row["window_max"]
        window_min = row["window_min"]
        drop_pct = (current_price - window_min) / window_min
        rise_pct = (current_price - window_max) / window_max

        latest_event = np.nan
        if symbol in event_map:
            latest_event = event_map[symbol]

        state_rows.append({
            "symbol": symbol,
            "company_name": company_name,
            "current_price": current_price,
            "window_max": window_max,
            "window_min": window_min,
            "drop_pct": drop_pct if drop_pct < 0 else "-", # only show drop_pct if it's a drop
            "rise_pct": rise_pct if rise_pct > 0 else "-", # only show rise_pct if it's a rise
            "latest_event": latest_event,
            "check_time": datetime.now().isoformat(timespec="seconds"),
        })


    return pd.DataFrame(state_rows)

# -----------------------------------------------------------------------------
#                      End of helper functions for main.py
#-----------------------------------------------------------------------------

def main():
    args = parse_args()

    # Check if market is open: if not, exit without polling prices
    if not args.force_run and not is_market_open_now():
        print("Outside trading hours. Exiting without polling prices.")
        return

    # Load stock list
    stock_df = pd.read_csv(args.stock_file)
    symbol_to_name = symbol_to_name_map(stock_df) # Build a symbol to company name mapping for notification messages and state table
    if "symbol" not in stock_df.columns:
        raise RuntimeError("Stock list file must contain a 'symbol' column.") # Exception handling
    symbols = stock_df["symbol"].dropna().unique().tolist()
    
    # Poll prices and detect events
    price_df = poll_prices(symbols, args.days)
    events = detect_events(price_df, args.threshold, symbol_to_name)

    # Send notifications for detected events
    if events:
        send_notifications(events, args.days, args.threshold)
        print(f"Generated {len(events)} notification(s).")
    else:
        print("No events detected.")

    # Build the state table and save to .csv
    state_df = build_state_table(price_df, events, symbol_to_name)
    state_df.to_csv(args.state_file, index=False)
    print(f"Saved current state to {args.state_file}")

if __name__ == "__main__":
    main()
