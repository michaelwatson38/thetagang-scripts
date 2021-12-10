#!/usr/bin/env python
"""Send earnings reports from @EPSGUID to Discord."""
import logging
import os
import sys
import re

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


def create_discord_message(message):
    """Publish a Discord message based on the earnings report."""
    webhook = DiscordWebhook(
        url=WEBHOOK_URL,
        content=message,
        username="Earnings Bot 💰",
        rate_limit_retry=True
    )
    return webhook.execute()


def recently_traded(symbol):
    """Check if a ticker was recently traded on thetagang.com."""
    url = "https://api.thetagang.com/trades"
    params = {"ticker": symbol}
    trades = requests.get(url, params=params).json()['data']['trades']

    # Skip this message if nobody has traded this ticker.
    if trades:
        logging.info(
            f"Found {len(trades)} trades on thetagang.com for {symbol}"
        )
    else:
        logging.info(f"Message skipped due to no trades for {symbol}")
        return False

    return True


class EarningsPublisher(object):
    """Send earnings events to Discord."""

    def get_consensus(self):
        """Get consensus for the earnings."""
        regex = r"consensus was (\(?\$[0-9\.]+\)?)"
        result = re.findall(regex, self.tweet_text)

        # Some earnings reports for smaller stocks don't have a consensus.
        if not result:
            return None

        # Parse the consensus and handle negative numbers.
        raw_consensus = result[0]
        if "(" in raw_consensus:
            # We have an expected loss.
            consensus = float(re.findall(r"[0-9\.]+", raw_consensus)[0]) * -1
        else:
            # We have an expected gain.
            consensus = float(re.findall(r"[0-9\.]+", raw_consensus)[0])

        return consensus

    def get_earnings(self):
        """Get earnings or loss data."""
        # Look for positive earnings by default.
        regex = r"reported (?:earnings of )?\$([0-9\.]+)"

        # Sometimes there's a loss. 😞
        if "reported a loss of" in self.tweet_text:
            regex = r"reported a loss of \$([0-9\.]+)"

        result = re.findall(regex, self.tweet_text)

        if result:
            return float(result[0])

        return None

    def get_emoji(self, earnings, consensus):
        """Return an emoji based on the earnings outcome."""
        if not consensus:
            return "🤷🏻‍♂️"
        elif earnings < consensus:
            return "🔴"
        else:
            return "🟢"

    def get_ticker(self):
        """Extract ticker from the tweet text."""
        result = re.findall(r'^\$([A-Z]+)', self.tweet_text)

        if result:
            return result[0]

        return None

    def parse(self):
        """Parse tweet data."""
        # Parse the stock ticker.
        ticker = self.get_ticker()
        if not ticker:
            return None

        # Earnings or a loss?
        earnings = self.get_earnings()

        # Get the earnings concensus.
        consensus = self.get_consensus()

        # Get an emoji based on the earnings outcome.
        emoji = self.get_emoji(earnings, consensus)

        return {
            "ticker": ticker,
            "earnings": earnings,
            "consensus": consensus,
            "emoji": emoji
        }

    def generate_message(self, tweet):
        """Generate a discord message based on the earnings result."""
        self.tweet_text = tweet['text']

        parsed = self.parse()
        if not parsed:
            return None

        message = (
            f"{parsed['emoji']} **{parsed['ticker']}**: `{parsed['earnings']}`"
            f" (expected: `{parsed['consensus'] or 'unknown'}`)"
        )

        return message


# Create a class to handle stream events.
class IDPrinter(tweepy.Stream):

    def on_status(self, status):
        raw_data = status._json

        if raw_data['retweeted'] or "RT @" in raw_data['text']:
            logging.info("Found a retweet, skipping...")
            logging.info(raw_data['text'])
            return

        ep = EarningsPublisher()
        parsed = ep.generate_message(raw_data)

        if not parsed:
            logging.info(f"🤷🏻‍♂️ Parse failed on {raw_data['text']}")
            return

        # if not recently_traded(parsed['ticker']):
        #     logging.info(f"⭕ No recent trades for {parsed['ticker']}")
        #     return

        logging.info(f"📤 Sending discord message for {parsed['ticker']}")
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
