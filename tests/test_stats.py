import asyncio
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import stats


class FakeResponse:
    def __init__(self, status=200, body="ok"):
        self.status = status
        self._body = body

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def text(self):
        return self._body

    def raise_for_status(self):
        if self.status >= 400:
            raise RuntimeError(f"HTTP {self.status}")


class FakeSession:
    def __init__(self, response):
        self._response = response
        self.patch_calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def patch(self, url, headers, json):
        self.patch_calls.append(
            {
                "url": url,
                "headers": headers,
                "json": json,
            }
        )
        return self._response


class StatsTestCase(unittest.TestCase):
    def setUp(self):
        stats._warned_missing_config = False
        stats._warned_invalid_manual_users = False

    def test_get_manual_users_count_valid_value(self):
        with patch.dict(os.environ, {"MANUAL_USERS": "42"}, clear=False):
            self.assertEqual(stats.get_manual_users_count(), 42)

    def test_get_manual_users_count_invalid_value_defaults_to_zero(self):
        with patch.dict(os.environ, {"MANUAL_USERS": "not-a-number"}, clear=False):
            self.assertEqual(stats.get_manual_users_count(), 0)

    def test_get_manual_users_count_negative_value_defaults_to_zero(self):
        with patch.dict(os.environ, {"MANUAL_USERS": "-9"}, clear=False):
            self.assertEqual(stats.get_manual_users_count(), 0)

    def test_update_stats_returns_false_without_gist_config(self):
        with patch.dict(
            os.environ,
            {
                "GIST_ID": "",
                "GIST_TOKEN": "",
            },
            clear=False,
        ):
            result = asyncio.run(
                stats.update_stats(
                    users=1,
                    guilds=1,
                    guild_users=1,
                    individual_users=0,
                )
            )

        self.assertFalse(result)

    def test_update_stats_sends_expected_payload(self):
        fake_response = FakeResponse(status=200, body="ok")
        fake_session = FakeSession(fake_response)

        with patch.dict(
            os.environ,
            {
                "GIST_ID": "gist123",
                "GIST_TOKEN": "token123",
                "GIST_FILENAME": "stats.json",
            },
            clear=False,
        ), patch.object(stats.aiohttp, "ClientSession", return_value=fake_session):
            result = asyncio.run(
                stats.update_stats(
                    users=10,
                    guilds=2,
                    guild_users=15,
                    individual_users=7,
                )
            )

        self.assertTrue(result)
        self.assertEqual(len(fake_session.patch_calls), 1)

        call = fake_session.patch_calls[0]
        self.assertEqual(call["url"], "https://api.github.com/gists/gist123")
        self.assertIn("Authorization", call["headers"])

        content = call["json"]["files"]["stats.json"]["content"]
        payload = json.loads(content)
        self.assertEqual(payload["users"], 10)
        self.assertEqual(payload["guilds"], 2)
        self.assertEqual(payload["guild_users"], 15)
        self.assertEqual(payload["individual_users"], 7)
        self.assertIn("updated_at", payload)


if __name__ == "__main__":
    unittest.main()
