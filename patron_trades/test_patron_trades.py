from datetime import datetime
import json
import unittest
from unittest import mock

import requests
import responses

from patron_trades import PatronTrades

class TestPatronTrades(unittest.TestCase):

    def test_get_pretty_expiry(self):
        """Test formatting of a pretty expiration date."""
        classobj = PatronTrades()

        # Try a date under 365 days away.
        current_year = datetime.now().strftime("%Y")
        ugly_date = f"{current_year}-11-01T19:21:10.111Z"
        pretty_date = classobj.get_pretty_expiry(ugly_date)
        self.assertEqual(pretty_date, "11/01")

        # Try a date over 365 days away.
        next_year = int(datetime.now().strftime("%Y")) + 2
        ugly_date = f"{next_year}-11-01T19:21:10.111Z"
        short_year = str(next_year)[2:]
        pretty_date = classobj.get_pretty_expiry(ugly_date)
        self.assertEqual(pretty_date, f"11/01/{short_year}")

    @responses.activate
    def test_get_trades_patron(self):
        """Ensure open patron trades are not filtered."""
        test_trades = [
            {
                "User": {
                    "role": "patron"
                },
                "close_date": None
            }
        ]
        responses.add(
            responses.GET,
            "https://api.thetagang.com/trades",
            json={'status': 200, 'data': {'trades': test_trades}}
        )
        classobj = PatronTrades()
        classobj.get_trades()
        self.assertTrue(classobj.latest_trades)

    @responses.activate
    def test_get_trades_non_patron(self):
        """Filter non-patron trades."""
        test_trades = [
            {
                "User": {
                    "role": "member"
                },
                "close_date": None
            }
        ]
        responses.add(
            responses.GET,
            "https://api.thetagang.com/trades",
            json={'status': 200, 'data': {'trades': test_trades}}
        )
        classobj = PatronTrades()
        classobj.get_trades()
        self.assertFalse(classobj.latest_trades)

    @responses.activate
    def test_get_trades_closed(self):
        """Filter closed trades."""
        test_trades = [
            {
                "User": {
                    "role": "patron"
                },
                "close_date": "somedate"
            }
        ]
        responses.add(
            responses.GET,
            "https://api.thetagang.com/trades",
            json={'status': 200, 'data': {'trades': test_trades}}
        )
        classobj = PatronTrades()
        classobj.get_trades()
        self.assertFalse(classobj.latest_trades)

    @responses.activate
    def test_get_trades_sort(self):
        """Test the sorting of trades."""
        test_trades = [
            {
                "type": "CASH SECURED PUT",
                "User": {
                    "role": "patron"
                },
                "close_date": None
            },
            {
                "type": "COVERED CALL",
                "User": {
                    "role": "patron"
                },
                "close_date": None
            }
        ]
        responses.add(
            responses.GET,
            "https://api.thetagang.com/trades",
            json={'status': 200, 'data': {'trades': test_trades}}
        )
        classobj = PatronTrades()
        classobj.get_trades()
        self.assertEqual(
            [x['type'] for x in classobj.latest_trades],
            sorted([x['type'] for x in test_trades], reverse=True),
        )
