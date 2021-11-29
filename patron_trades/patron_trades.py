#!/usr/bin/env python
"""Relay trades from thetagang.com Patrons to Discord."""
from datetime import datetime
import json
import logging
import os
import sys
import time

from dateutil.parser import parse
from discord_webhook import DiscordWebhook, DiscordEmbed
import requests


# Set up logging.
logging.basicConfig(
    stream=sys.stdout,
    level=logging.DEBUG,
    format="%(asctime)s;%(levelname)s;%(message)s"
)


class PatronTrades:
    """Relay trades from thetagang.com Patrons to Discord."""

    def __init__(self):
        """Startup tasks."""
        self.first_run = True
        self.seen_trades = []
        self.webhook_url = os.environ.get('WEBHOOK_URL')

    def get_trades(self):
        """Download the latest set of trades from thetagang.com."""
        url = "https://api.thetagang.com/trades"
        resp = requests.get(url)
        raw_trades = resp.json()['data']['trades']

        # Keep only patron trades that are opening trades.
        valid_trades = [
            x for x in raw_trades
            if x['User']['role'] == 'patron' and x['close_date'] is None
        ]
        valid_trades.reverse()

        self.latest_trades = valid_trades

    def get_pretty_expiry(self, date_string):
        """Take a date string from JSON and make a pretty expiry date string."""
        # Get DTE.
        parsed_date = parse(date_string, ignoretz=True)
        dte = (parsed_date - datetime.now()).days

        # Only show month/date if the option expires in less than 365 days.
        if dte <= 365:
            return parsed_date.strftime("%m/%d")

        return parsed_date.strftime("%m/%d/%y")

    def get_trade_data(self, trade):
        """Return trade data."""
        # Get the most basic information.
        data = {
            "trade_type": trade['type'],
            "user": trade['User']['username'],
            "user_url": f"https://thetagang.com/{trade['User']['username']}",
            "symbol": trade['symbol'].upper(),
            "price": "{:,.2f}".format(trade['price_filled']),
            "guid": trade['guid'],
            "expiry": None,
            "quantity": trade['quantity'],
            "note": trade['note']
        }

        # Options trades have expiry dates.
        if trade['expiry_date']:
            data['expiry'] = self.get_pretty_expiry(trade['expiry_date'])

        # Get the strikes provided.
        data['strikes'] = {
            "short put": trade['short_put'],
            "short call": trade['short_call'],
            "long put": trade['long_put'],
            "long call": trade['long_call'],
        }
        data['strikes_string'] = '/'.join([
            f"${v}" for k,v in data['strikes'].items() if v is not None
        ]).capitalize()

        return data

    def send_discord_webhook(self, data):
        """Send the trade message to Discord."""
        webhook = DiscordWebhook(
            url=self.webhook_url,
            username="Trades Bot 📈",
            rate_limit_retry=True
        )
        embed = DiscordEmbed(
            title=(
                f"${data['symbol']}: {data['strikes_string']} "
                f"{data['trade_type']} for ${data['price']} "
                f"expiring {data['expiry']} "
            ),
            description=(
                f"Quantity: {data['quantity']}. "
                f"Opened by [{data['user']}]({data['user_url']})."
            ),
            color='008000',
            url=f"https://thetagang.com/{data['user']}/{data['guid']}"
        )
        embed.set_footer(
            text=f"Trade notes: {data['note']}"
        )
        webhook.add_embed(embed)
        webhook.execute()

    def run(self):
        """Run the trade relay."""
        logging.info("Getting new trades from thetagang.com...")
        self.get_trades()

        # Loop through the latest trades.
        for trade in self.latest_trades:
            data = self.get_trade_data(trade)

            # Skip this trade if we've seen it before.
            if trade['guid'] in self.seen_trades:
                logging.info(f"Trade {trade['guid']} was seen before")
                continue

            # Skip alerts if we are running the script for the first time.
            if not self.first_run:
                self.send_discord_webhook(data)

            # Add this trade to the list of seen trades.
            logging.info(f"Adding {trade['guid']} to the list of seen trades")
            self.seen_trades.append(trade['guid'])

        # We've completed the first run by this point.
        self.first_run = False

        # Sleep for five minutes and run again.
        time.sleep(300)
        self.run()


if __name__ == "__main__":
    classObj = PatronTrades()
    classObj.run()
