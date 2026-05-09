from datetime import datetime

def format_notification_line(event: dict):
   
    """
    Write one line for a stock price alert event to a sentence.
    @ params[in]:
        event: A dictionary that contains alert details.
                Expected keys:
                - symbol
                - company_name
                - current_price
                - reference_price
                - event_type
                - change_pct
                - message
    @ return: string line for one event, e.g. "Apple Inc. (AAPL)'s price rose by 15.00% compared to the recent maximum price."
    """

    symbol = event["symbol"]
    company_name = event.get("company_name", "")

    if not company_name:
        company_name = symbol

    event_type = event["event_type"]
    change_pct = event["change_pct"]

    if event_type == "DROP":
        action_word = "dropped"
        reference_word = "minimum"
        display_pct = abs(change_pct)
    elif event_type == "RISE":
        action_word = "rose"
        reference_word = "maximum"
        display_pct = change_pct

    line = (f"{company_name} ({symbol})'s price {action_word} by {display_pct:.2%} compared to the recent {reference_word} price.")

    return line


def send_notifications(events: list[dict], window_days: int, threshold: float, output_file: str = "notifications"):
    """
    Write stock price alert events to a local notification log file.
    The notification format is:
    Timestamp: [timestamp]
    Check Window: [window_days] day(s)
    Threshold: [threshold]%
    [space line]
    [space line]
    [company name] ([symbol])'s price [rose/dropped] by [pct]% compared to the recent [maximum/minimum] price.

    @ Params[in]:
        events: A list of dictionaries, each containing alert details for one stock. Expected keys in
                each dictionary:
                - symbol
                - company_name
                - current_price
                - reference_price
                - event_type
                - change_pct
                - message
        window_days: The number of recent calendar days used to calculate high and low prices. This is included in the notification for context.
        threshold: The price movement threshold used to trigger the alert. This is included in the notification for context.
        output_file: The base name of the output file where notifications will be saved. The actual file name will have a timestamp appended to it. Default is "notifications".
     @ return: void. The function writes the notifications to a local file.
    
    """

    timestamp = datetime.now().isoformat(timespec="seconds")

    lines = []
    lines.append(f"Timestamp: {timestamp}")
    lines.append(f"Check Window: {window_days} day(s)")
    lines.append(f"Threshold: {threshold:.2%}")
    lines.append("")
    lines.append("")

    for event in events:
        lines.append(format_notification_line(event))

    lines.append("")

    output_file_timestamp = output_file + "_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".log"
    with open(output_file_timestamp, "a", encoding="utf-8") as file:
        file.write("\n".join(lines))
        file.write("\n")

