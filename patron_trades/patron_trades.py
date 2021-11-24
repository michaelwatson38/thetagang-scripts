#!/usr/bin/env python
from datetime import datetime
import json
import logging
import os
import sys
import time

from dateutil.parser import parse
from discord_webhook import DiscordWebhook
import requests

# Make an empty list of trades we've already seen.
seen_trades = []

# The Discord webhook URL where messages should be sent. For threads, append
# ?thread_id=1234567890 to the end of the URL.
WEBHOOK_URL = os.environ.get('WEBHOOK_URL')

# Set up logging.
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s;%(levelname)s;%(message)s"
)


def generate_trade_message(trade):
    """Parse a trade and generate a Discord message."""
    if trade['type'] in ['CASH SECURED PUT', 'COVERED CALL', 'SHORT NAKED CALL']:
        return single_leg_credit(trade)

    if trade['type'] in ['LONG NAKED CALL', 'LONG NAKED PUT']:
        return single_leg_debit(trade)

    if trade['type'] in ['PUT CREDIT SPREAD', 'CALL CREDIT SPREAD']:
        return spread_credit(trade)

    if trade['type'] in ['PUT DEBIT SPREAD', 'CALL DEBIT SPREAD']:
        return spread_debit(trade)

    if "COMMON STOCK" in trade['type']:
        return common_stock(trade)

    if "STRANGLE" in trade['type']:
        return common_stock(trade)

    return None


def get_pretty_expiry(date_string):
    """Take a date string from JSON and make a pretty expiry date string."""
    # Get DTE.
    parsed_date = parse(date_string, ignoretz=True)
    dte = (parsed_date - datetime.now()).days

    # Only show month/date if the option expires in less than 365 days.
    if dte <= 365:
        return parsed_date.strftime("%m/%d")

    return parsed_date.strftime("%m/%d/%y")


def common_stock(trade):
    """Generate a message for stock transactions."""
    trade_type = trade['type'].lower()
    user = trade['User']['username']
    symbol = trade['symbol'].upper()
    price = "${:,.2f}".format(trade['price_filled'])
    quantity = trade['quantity']

    action = "bought" if "buy" in trade_type else "sold"

    return f"{user} {action} {quantity} shares of ${symbol} at {price}"


def single_leg_credit(trade):
    """Generate a message for a single leg credit trade."""
    action = "closed" if trade['close_date'] else "opened"
    trade_type = trade['type'].lower()
    user = trade['User']['username']
    strike = trade['short_put'] if "put" in trade_type else trade['short_call']
    symbol = trade['symbol'].upper()
    expiry = get_pretty_expiry(trade['expiry_date'])
    qty = trade['quantity']
    premium = trade['price_filled']
    
    return (
        f"{user} {action} {qty} {trade_type} on ${symbol} at ${strike} for ${premium} "
        f"expiring {expiry}"
    )


def single_leg_debit(trade):
    """Generate a message for a single leg debit trade."""
    action = "closed" if trade['close_date'] else "opened"
    trade_type = trade['type'].lower()
    user = trade['User']['username']
    strike = trade['long_put'] if "put" in trade_type else trade['long_call']
    symbol = trade['symbol'].upper()
    expiry = get_pretty_expiry(trade['expiry_date'])
    qty = trade['quantity']
    premium = trade['price_filled']
    
    return (
        f"{user} {action} {qty} {trade_type} on ${symbol} at ${strike} for ${premium} "
        f"expiring {expiry}"
    )


def spread_credit(trade):
    """Generate a message for a credit spread."""
    action = "closed" if trade['close_date'] else "opened"
    trade_type = trade['type'].lower()
    user = trade['User']['username']
    short_strike = (
        trade['short_put'] if "put" in trade_type else trade['short_call']
    )
    long_strike = (
        trade['long_put'] if "put" in trade_type else trade['long_call']
    )
    symbol = trade['symbol'].upper()
    expiry = get_pretty_expiry(trade['expiry_date'])
    qty = trade['quantity']
    premium = trade['price_filled']
    
    return (
        f"{user} {action} {qty} {trade_type} on ${symbol} for ${premium} expiring {expiry} "
        f"(short: ${short_strike} long: ${long_strike})"
    )

def spread_debit(trade):
    """Generate a message for a debit spread."""
    action = "closed" if trade['close_date'] else "opened"
    trade_type = trade['type'].lower()
    user = trade['User']['username']
    short_strike = (
        trade['short_put'] if "put" in trade_type else trade['short_call']
    )
    long_strike = (
        trade['long_put'] if "put" in trade_type else trade['long_call']
    )
    symbol = trade['symbol'].upper()
    expiry = get_pretty_expiry(trade['expiry_date'])
    qty = trade['quantity']
    premium = trade['price_filled']
    
    return (
        f"{user} {action} {qty} {trade_type} on ${symbol} for ${premium} expiring {expiry} "
        f"(short: ${short_strike} long: ${long_strike})"
    )

def strangle(trade):
    """Generate a message for a strangle."""
    action = "closed" if trade['close_date'] else "opened"
    trade_type = trade['type'].lower()
    user = trade['User']['username']
    call_strike = (
        trade['short_call'] if "short" in trade_type else trade['long_call']
    )
    put_strike = (
        trade['short_put'] if "short" in trade_type else trade['long_put']
    )
    symbol = trade['symbol'].upper()
    expiry = get_pretty_expiry(trade['expiry_date'])
    qty = trade['quantity']
    premium = trade['price_filled']
    
    return (
        f"{user} {action} {qty} {trade_type} on ${symbol} for ${premium} expiring {expiry} "
        f"(call: ${call_strike} put: ${put_strike})"
    )



while True:
    url = "https://api.thetagang.com/trades"
    trades = requests.get(url).json()['data']['trades']

    # Start with the oldest first.
    trades.reverse()

    # Are we on the first run after startup?
    first_run = True if not seen_trades else False

    # Create an empty list to hold messages.
    messages = []

    # Create an empty string to hold the webhook content.
    webhook_content = ""

    for trade in trades:
        # Only show patron trades.
        if trade['User']['role'] == 'member':
            continue

        # Set a trade key that we can use as a marker for trades we've seen.
        action = "closed" if trade['close_date'] else "opened"
        trade_key = f"{trade['guid']}-{action}"
        if trade_key in seen_trades:
            continue

        # Build a message based on the trade data.
        message = generate_trade_message(trade)

        # Print a failure if we caught a trade we couldn't parse
        if not message:
            print("🤷🏻‍♂️ Not sure how to handle:")
            print(json.dumps(trade, indent=2))

        # Append the URL to the trade at the end of the message.
        message = (
            f"{message} https://thetagang.com/{trade['User']['username']}"
            f"/{trade['guid']}"
        )

        # Add the current message onto our list of messages.
        print(message)
        messages.append(message)

        # Add this trade to the list of seen trades.
        logging.info(f"Adding {trade_key} to list of seen trades")
        seen_trades.append(trade_key)

    # Handle messages depending on how many we have.
    if len(messages) == 1:
        # Just one? Send it through as is:
        webhook_content = messages[0]
    elif len(messages) > 1:
        # Multiple trades? Batch them to avoid Discord rate limits.
        webhook_content = "Multiple trades:\n" + "\n".join(messages)

    # Send the message to Discord if we're not on the first run and we have
    # messages to send.
    if messages and not first_run:
        webhook = DiscordWebhook(
            url=WEBHOOK_URL,
            content=webhook_content,
            username="Trades Bot 📈",
            rate_limit_retry=True
        )
        webhook.execute()

    # Clear the list of messages.
    messages = []

    # Clear our first run marker.
    first_run = False

    # Sleep.
    logging.info("💤 Sleeping for 5 minutes")
    time.sleep(300)
