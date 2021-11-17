#!/usr/bin/env python
"""Monitor thetagang.com trends and notify the Discord."""
import logging
import os
import sys
import time

from discord_webhook import DiscordWebhook
import requests

# The Discord webhook URL where messages should be sent. For threads, append
# ?thread_id=1234567890 to the end of the URL.
WEBHOOK_URL = os.environ.get('WEBHOOK_URL')

trends_url = "https://api.thetagang.com/trends"
trends = []

logging.basicConfig(
    stream=sys.stdout,
    level=logging.DEBUG,
    format="%(asctime)s;%(levelname)s;%(message)s"
)


def get_trends():
    """Get the latest trends from thetagang.com."""
    trends = requests.get(trends_url).json()['data']['trends']
    return trends


def create_discord_message(ticker):
    """Send a message to the thetagang discord."""
    message = f"**${ticker}** https://thetagang.com/symbols/{ticker}"
    webhook = DiscordWebhook(
        content=message,
        url=WEBHOOK_URL,
        username="Trends Bot 🚀",
        rate_limit_retry=True
    )
    return webhook.execute()


while True:
    # Get the current list of trending tickers.
    current_trends = get_trends()

    # Find any tickers that are new since the last check.
    new_trends = [x for x in current_trends if x not in trends]

    # Extra logging.
    logging.info(f"Latest trends: {current_trends}")
    logging.info(f"Previous trends: {trends}")
    logging.info(f"New trends: {new_trends}")

    # Avoid blasting the chat when the container restarts. Look for an empty old
    # trends list and a new trends list with more than one trend already in it.
    if not trends and len(new_trends) > 1:
        logging.info(
            f"🛑 Skipping {len(new_trends)} new trends after restart"
        )
    else:
        # Send Discord messages for the new trends.
        for ticker in new_trends:
            create_discord_message(ticker)

    # Store the current trends list.
    trends = current_trends

    # Sleep for a while.
    time.sleep(300)
