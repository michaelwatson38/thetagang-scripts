#!/usr/bin/env python
"""Send earnings reports from @EPSGUID to Discord."""
import logging
import os
import sys

from discord_webhook import DiscordWebhook
import requests
import tweepy


# The Discord webhook URL where messages should be sent. For threads, append
# ?thread_id=1234567890 to the end of the URL.
WEBHOOK_URL = os.environ.get('WEBHOOK_URL')

# Twitter developer credentials.
consumer_key = os.environ.get('CONSUMER_KEY')
consumer_secret = os.environ.get('CONSUMER_SECRET')
access_token = os.environ.get('ACCESS_TOKEN')
access_token_secret = os.environ.get('ACCESS_TOKEN_SECRET')

# Set up logging.
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s;%(levelname)s;%(message)s"
)

def create_discord_message(parsed):
    """Generate a Discord message based on the earnings report."""
    message = f"{parsed['emoji']} {parsed['text']}"
    webhook = DiscordWebhook(
        url=WEBHOOK_URL,
        content=message,
        username="Earnings Bot 💰",
        rate_limit_retry=True
    )
    return webhook.execute()


def get_emoji(hashtag):
    """Return a helpful emoji bashed on the hashtag of the earning report."""
    if "miss" in hashtag:
        return "🔴"

    return "🟢"


def parse_earnings(tweet_json):
    """Extract some metadata from the earning report tweet."""
    try:
        details = {
            "symbol": tweet_json['entities']['symbols'][0]['text'],
            "hashtag": tweet_json['entities']['hashtags'][0]['text'],
            "text": tweet_json['text']
        }
        details['emoji'] = get_emoji(details['hashtag'])

    except IndexError:
        # We don't want any tweets without hashtags.
        return None

    # Avoid tweets like these:
    # https://twitter.com/EPSGUID/status/1466128053034176515
    if details["hashtag"] in ['earnings', 'volatility']:
        return None

    return details


def recently_traded(symbol):
    """Check if a ticker was recently traded on thetagang.com."""
    url = "https://api.thetagang.com/trades"
    params = {"ticker": symbol}
    trades = requests.get(url, params=params).json()['data']['trades']

    # Skip this message if nobody has traded this ticker.
    if trades:
        logging.info(f"Found {len(trades)} trades on thetagang.com for {symbol}")
    else:
        logging.info(f"Message skipped due to no trades for {symbol}")
        return False

    return True


# Create a class to handle stream events.
class IDPrinter(tweepy.Stream):

    def on_status(self, status):
        raw_data = status._json

        if raw_data['retweeted'] or "RT @" in raw_data['text']:
            logging.info("Found a retweet, skipping...")
            logging.info(raw_data['text'])
            return

        parsed = parse_earnings(raw_data)

        if not parsed:
            logging.info(f"🤷🏻‍♂️ Parse failed on {raw_data['text']}")
            return

        if not recently_traded(parsed['symbol']):
            logging.info(f"⭕ No recent trades for {parsed['symbol']}")
            return

        logging.info(f"📤 Sending discord message for {parsed['symbol']}")
        create_discord_message(parsed)


# Print a message to Discord noting that we started up.
logging.info('Starting up...')

# Initialize instance of the subclass
printer = IDPrinter(
  consumer_key, consumer_secret,
  access_token, access_token_secret
)

# Follow @EPSGUID tweets.
printer.filter(follow=[55395551])

# Print a message to Discord noting that we shut down.
logging.info('Shutting down...')
