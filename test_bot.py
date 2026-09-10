#!/usr/bin/env python3
"""
Unit tests for the bKash/Nagad SMS Telegram Forwarder Bot (bot.py).
"""

import asyncio
import json
import os
import shutil
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from bot import (
    FALLBACK_TRX_REGEX,
    TK_REGEX_1,
    TK_REGEX_2,
    TRX_REGEX,
    get_saved_chat_ids,
    handle_webhook,
    save_chat_id,
)


class TestHyperBot(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.chat_ids_path = os.path.join(self.test_dir, "chat_ids.json")
        self.patcher_chat_ids = patch("bot.CHAT_IDS_FILE", self.chat_ids_path)
        self.patcher_legacy = patch("bot.LEGACY_CHAT_ID_FILE", os.path.join(self.test_dir, "chat_id.txt"))
        self.patcher_chat_ids.start()
        self.patcher_legacy.start()

        # Clear global state
        import bot
        bot.SAVED_CHAT_IDS = set()

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.patcher_chat_ids.stop()
        self.patcher_legacy.stop()
        shutil.rmtree(self.test_dir)
        self.loop.close()

    def test_regex_trx_extraction(self):
        # bKash format test
        bkash_sms = "You have received Tk 500.00 from 01711000000. Ref 1. Fee Tk 0.00. Balance Tk 1500.00. TrxID BKA12345678 at 10/09/2026 14:00"
        m = TRX_REGEX.search(bkash_sms)
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), "BKA12345678")

        tk_m = TK_REGEX_1.search(bkash_sms)
        self.assertIsNotNone(tk_m)
        self.assertEqual(tk_m.group(1), "500.00")

    def test_fallback_regex(self):
        sms = "Payment received. ID: 9A8B7C6D5E"
        m = FALLBACK_TRX_REGEX.search(sms)
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), "9A8B7C6D5E")

    def test_save_and_get_chat_ids(self):
        save_chat_id("123456789")
        ids = get_saved_chat_ids()
        self.assertIn("123456789", ids)

        # Ensure persistence to file
        self.assertTrue(os.path.exists(self.chat_ids_path))
        with open(self.chat_ids_path, "r") as f:
            saved_data = json.load(f)
            self.assertIn("123456789", saved_data)

    def test_handle_webhook_valid_sms(self):
        request = MagicMock()
        request.method = "POST"
        request.content_type = "application/json"
        request.query = {}
        request.json = AsyncMock(return_value={
            "message": "You have received Tk 1,200.00 from 01800000000. TrxID NAGAD998877"
        })
        request.text = AsyncMock(return_value="")

        with patch("bot.broadcast_telegram_message", new_callable=AsyncMock) as mock_broadcast:
            response = self.loop.run_until_complete(handle_webhook(request))
            self.assertEqual(response.status, 200)
            res_json = json.loads(response.body.decode("utf-8"))
            self.assertEqual(res_json["status"], "success")
            self.assertEqual(res_json["trx_id"], "NAGAD998877")
            self.assertEqual(res_json["amount"], "1,200.00")

    def test_handle_webhook_ignored_sms(self):
        request = MagicMock()
        request.method = "POST"
        request.content_type = "application/json"
        request.query = {}
        request.json = AsyncMock(return_value={"message": "Good morning! Hope you have a great day."})
        request.text = AsyncMock(return_value="")

        response = self.loop.run_until_complete(handle_webhook(request))
        self.assertEqual(response.status, 200)
        res_json = json.loads(response.body.decode("utf-8"))
        self.assertEqual(res_json["status"], "ignored")


if __name__ == "__main__":
    unittest.main()
