#!/usr/bin/env python3
"""
Unit tests for the Telegram Group Bot.
"""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from telegram import ChatPermissions
from telegram.constants import ChatMemberStatus

from group_bot import (
    ban_user,
    extract_status_change,
    filter_bad_words,
    greet_chat_members,
    group_info,
    is_admin,
    kick_user,
    mute_user,
    rules,
    unmute_user,
    invite_link,
)


class TestTelegramGroupBot(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    def test_is_admin_private(self):
        update = MagicMock()
        update.effective_chat.type = "private"
        context = MagicMock()

        res = self.loop.run_until_complete(is_admin(update, context))
        self.assertTrue(res)

    def test_is_admin_group_admin(self):
        update = MagicMock()
        update.effective_chat.type = "supergroup"
        update.effective_user.id = 123
        member = MagicMock()
        member.status = ChatMemberStatus.ADMINISTRATOR
        update.effective_chat.get_member = AsyncMock(return_value=member)
        context = MagicMock()

        res = self.loop.run_until_complete(is_admin(update, context))
        self.assertTrue(res)
        update.effective_chat.get_member.assert_called_once_with(123)

    def test_is_admin_group_regular(self):
        update = MagicMock()
        update.effective_chat.type = "supergroup"
        update.effective_user.id = 456
        member = MagicMock()
        member.status = ChatMemberStatus.MEMBER
        update.effective_chat.get_member = AsyncMock(return_value=member)
        context = MagicMock()

        res = self.loop.run_until_complete(is_admin(update, context))
        self.assertFalse(res)
        update.effective_chat.get_member.assert_called_once_with(456)

    def test_rules_command(self):
        update = MagicMock()
        update.message.reply_text = AsyncMock()
        context = MagicMock()

        self.loop.run_until_complete(rules(update, context))
        update.message.reply_text.assert_called_once()
        self.assertIn("Group Rules", update.message.reply_text.call_args[0][0])

    def test_group_info_private(self):
        update = MagicMock()
        update.effective_chat.type = "private"
        update.message.reply_text = AsyncMock()
        context = MagicMock()

        self.loop.run_until_complete(group_info(update, context))
        update.message.reply_text.assert_called_once_with("❌ This command can only be used in groups.")

    def test_group_info_group(self):
        update = MagicMock()
        update.effective_chat.type = "supergroup"
        update.effective_chat.title = "Test Group"
        update.effective_chat.id = -10012345
        update.effective_chat.get_member_count = AsyncMock(return_value=42)
        update.message.reply_text = AsyncMock()
        context = MagicMock()

        self.loop.run_until_complete(group_info(update, context))
        update.message.reply_text.assert_called_once()
        self.assertIn("Test Group", update.message.reply_text.call_args[0][0])
        self.assertIn("-10012345", update.message.reply_text.call_args[0][0])
        self.assertIn("42", update.message.reply_text.call_args[0][0])

    def test_extract_status_change_join(self):
        chat_member_update = MagicMock()
        chat_member_update.difference.return_value = {"status": (ChatMemberStatus.LEFT, ChatMemberStatus.MEMBER)}
        res = extract_status_change(chat_member_update)
        self.assertEqual(res, (False, True))

    def test_extract_status_change_leave(self):
        chat_member_update = MagicMock()
        chat_member_update.difference.return_value = {"status": (ChatMemberStatus.MEMBER, ChatMemberStatus.LEFT)}
        res = extract_status_change(chat_member_update)
        self.assertEqual(res, (True, False))

    @patch("group_bot.extract_status_change")
    def test_greet_chat_members_join(self, mock_extract):
        mock_extract.return_value = (False, True)
        update = MagicMock()
        update.chat_member.new_chat_member.user.first_name = "Alice"
        update.effective_chat.send_message = AsyncMock()
        context = MagicMock()

        self.loop.run_until_complete(greet_chat_members(update, context))
        update.effective_chat.send_message.assert_called_once()
        self.assertIn("Welcome Alice", update.effective_chat.send_message.call_args[0][0])

    @patch("group_bot.extract_status_change")
    def test_greet_chat_members_leave(self, mock_extract):
        mock_extract.return_value = (True, False)
        update = MagicMock()
        update.chat_member.new_chat_member.user.first_name = "Bob"
        update.effective_chat.send_message = AsyncMock()
        context = MagicMock()

        self.loop.run_until_complete(greet_chat_members(update, context))
        update.effective_chat.send_message.assert_called_once()
        self.assertIn("Bob has left", update.effective_chat.send_message.call_args[0][0])

    @patch("group_bot.is_admin")
    def test_filter_bad_words_admin_exempt(self, mock_is_admin):
        mock_is_admin.return_value = True
        update = MagicMock()
        update.message.text = "this is a scamlink post"
        update.message.delete = AsyncMock()
        context = MagicMock()

        self.loop.run_until_complete(filter_bad_words(update, context))
        update.message.delete.assert_not_called()

    @patch("group_bot.is_admin")
    def test_filter_bad_words_user_removed(self, mock_is_admin):
        mock_is_admin.return_value = False
        update = MagicMock()
        update.message.text = "this is a scamlink post"
        update.message.delete = AsyncMock()
        update.effective_user.first_name = "Scammer"
        update.effective_chat.send_message = AsyncMock()
        context = MagicMock()

        self.loop.run_until_complete(filter_bad_words(update, context))
        update.message.delete.assert_called_once()
        update.effective_chat.send_message.assert_called_once()
        self.assertIn("your message was removed", update.effective_chat.send_message.call_args[0][0])

    @patch("group_bot.is_admin")
    def test_kick_user_success(self, mock_is_admin):
        mock_is_admin.return_value = True
        update = MagicMock()
        update.message.reply_to_message.from_user.first_name = "Charlie"
        update.message.reply_to_message.from_user.id = 999
        update.effective_chat.id = -100
        update.message.reply_text = AsyncMock()
        context = MagicMock()
        context.bot.ban_chat_member = AsyncMock()
        context.bot.unban_chat_member = AsyncMock()

        self.loop.run_until_complete(kick_user(update, context))
        context.bot.ban_chat_member.assert_called_once_with(chat_id=-100, user_id=999)
        context.bot.unban_chat_member.assert_called_once_with(chat_id=-100, user_id=999)
        update.message.reply_text.assert_called_once_with("👞 Successfully kicked Charlie.")

    @patch("group_bot.is_admin")
    def test_ban_user_success(self, mock_is_admin):
        mock_is_admin.return_value = True
        update = MagicMock()
        update.message.reply_to_message.from_user.first_name = "Dave"
        update.message.reply_to_message.from_user.id = 888
        update.effective_chat.id = -100
        update.message.reply_text = AsyncMock()
        context = MagicMock()
        context.bot.ban_chat_member = AsyncMock()

        self.loop.run_until_complete(ban_user(update, context))
        context.bot.ban_chat_member.assert_called_once_with(chat_id=-100, user_id=888)
        update.message.reply_text.assert_called_once_with("🚫 Successfully banned Dave.")

    @patch("group_bot.is_admin")
    def test_mute_user_success(self, mock_is_admin):
        mock_is_admin.return_value = True
        update = MagicMock()
        update.message.reply_to_message.from_user.first_name = "Eve"
        update.message.reply_to_message.from_user.id = 777
        update.effective_chat.id = -100
        update.message.reply_text = AsyncMock()
        context = MagicMock()
        context.bot.restrict_chat_member = AsyncMock()

        self.loop.run_until_complete(mute_user(update, context))
        context.bot.restrict_chat_member.assert_called_once()
        call_kwargs = context.bot.restrict_chat_member.call_args[1]
        self.assertEqual(call_kwargs["chat_id"], -100)
        self.assertEqual(call_kwargs["user_id"], 777)
        self.assertFalse(call_kwargs["permissions"].can_send_messages)
        update.message.reply_text.assert_called_once_with("🔇 Successfully muted Eve.")

    @patch("group_bot.is_admin")
    def test_unmute_user_success(self, mock_is_admin):
        mock_is_admin.return_value = True
        update = MagicMock()
        update.message.reply_to_message.from_user.first_name = "Frank"
        update.message.reply_to_message.from_user.id = 666
        update.effective_chat.id = -100
        update.message.reply_text = AsyncMock()
        context = MagicMock()
        context.bot.restrict_chat_member = AsyncMock()

        self.loop.run_until_complete(unmute_user(update, context))
        context.bot.restrict_chat_member.assert_called_once()
        call_kwargs = context.bot.restrict_chat_member.call_args[1]
        self.assertEqual(call_kwargs["chat_id"], -100)
        self.assertEqual(call_kwargs["user_id"], 666)
        self.assertTrue(call_kwargs["permissions"].can_send_messages)
        update.message.reply_text.assert_called_once_with("🔊 Successfully unmuted Frank.")

    def test_invite_link_private(self):
        update = MagicMock()
        update.effective_chat.type = "private"
        update.message.reply_text = AsyncMock()
        context = MagicMock()

        self.loop.run_until_complete(invite_link(update, context))
        update.message.reply_text.assert_called_once_with("❌ This command can only be used in groups.")

    def test_invite_link_success(self):
        update = MagicMock()
        update.effective_chat.type = "supergroup"
        update.effective_chat.id = -100123
        update.message.reply_text = AsyncMock()

        invite_link_obj = MagicMock()
        invite_link_obj.invite_link = "https://t.me/joinchat/ABC"

        context = MagicMock()
        context.bot.create_chat_invite_link = AsyncMock(return_value=invite_link_obj)

        self.loop.run_until_complete(invite_link(update, context))
        context.bot.create_chat_invite_link.assert_called_once_with(chat_id=-100123)
        update.message.reply_text.assert_called_once()
        self.assertIn("https://t.me/joinchat/ABC", update.message.reply_text.call_args[0][0])


if __name__ == "__main__":
    unittest.main()
