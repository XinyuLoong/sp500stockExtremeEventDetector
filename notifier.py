from datetime import datetime

def send_a_notification(event: dict, output_file: str = "notifications.log"):
    
    """
    Write one stock price alert event to a local notification log file.
    @ Params[in]:
        event: A dictionary that contains alert details.
                Expected keys:
                - symbol
                - company_name
                - current_price
                - reference_price
                - event_type
                - change_pct
                - message
        output_file: The log file used to store notifications.
    @ return: void
    """

    timestamp = datetime.now().isoformat(timespec="seconds")
    line = (
        f"{timestamp} | "
        f"{event['symbol']} | "
        f"{event['company_name']} | "
        f"{event['event_type']} | "
        f"current_price={event['current_price']:.2f} | "
        f"reference_price={event['reference_price']:.2f} | "
        f"change_pct={event['change_pct']:.2%} | "
        f"{event['message']}\n"
    )
    with open(output_file, "a", encoding="utf-8") as file:
        file.write(line)


def send_notifications(events: list[dict], output_file: str = "notifications.log"):
    """
    Write multiple stock price alert events to a local notification log file.
    @ Params[in]:
        events: A list of dictionaries, each containing alert details.
                Expected keys in each dictionary:
                - symbol
                - company_name
                - current_price
                - reference_price
                - event_type
                - change_pct
                - message
        output_file: The log file used to store notifications.
    @ return: void
    """
    for event in events:
        send_a_notification(event, output_file)