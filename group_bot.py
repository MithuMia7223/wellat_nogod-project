#!/usr/bin/env python3
"""
A Python Telegram Bot specialized for group chat management and interaction.
"""

import logging
import os
import sys
from dotenv import load_dotenv
from telegram import Update, ChatPermissions
from telegram.constants import ChatMemberStatus, ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    ChatMemberHandler,
    filters,
)

# Load environment variables from .env file
load_dotenv()

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[logging.StreamHandler(sys.stdout)],
)
# Set higher logging level for httpx to avoid excessive polling logs
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# List of banned/offensive words to filter out (case-insensitive)
BAD_WORDS = ["spamlink", "scam", "cheat", "badword123"]


async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Checks if the user sending the command is a group administrator/creator."""
    chat = update.effective_chat
    user = update.effective_user
    if not chat or not user:
        return False
    # If it is a private chat, we consider the user an admin
    if chat.type == "private":
        return True
    try:
        member = await chat.get_member(user.id)
        return member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)
    except Exception as e:
        logger.error(f"Error checking admin status: {e}")
        return False


async def check_admin_rights(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Replies and returns False if the user is not an administrator, True otherwise."""
    if not await is_admin(update, context):
        await update.message.reply_text("❌ You must be an administrator to run this command.")
        return False
    return True


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message and lists available commands."""
    welcome_text = (
        "👋 **Hello! I am your Group Manager Bot.**\n\n"
        "Add me to a group and promote me to Administrator to help manage your community.\n\n"
        "🤖 **Available Commands:**\n"
        "• `/rules` - View group rules\n"
        "• `/groupinfo` - View group statistics\n"
        "• `/invite` - Get group invite link to add users\n\n"
        "🛡️ **Admin Commands (Reply to a user's message):**\n"
        "• `/mute` - Mute a user\n"
        "• `/unmute` - Unmute a user\n"
        "• `/kick` - Kick a user\n"
        "• `/ban` - Ban a user"
    )
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN)


async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays the group rules."""
    rules_text = (
        "📜 **Group Rules:**\n\n"
        "1. Be respectful to other members.\n"
        "2. No spamming, flooding, or advertising.\n"
        "3. Keep discussions relevant to the group's topic.\n"
        "4. Follow instructions of administrators."
    )
    await update.message.reply_text(rules_text, parse_mode=ParseMode.MARKDOWN)


async def group_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays information about the group chat."""
    chat = update.effective_chat
    if not chat or chat.type == "private":
        await update.message.reply_text("❌ This command can only be used in groups.")
        return

    try:
        member_count = await chat.get_member_count()
        info_text = (
            f"ℹ️ **Group Information:**\n\n"
            f"👥 **Title:** {chat.title}\n"
            f"🆔 **Chat ID:** `{chat.id}`\n"
            f"💬 **Type:** {chat.type.capitalize()}\n"
            f"📈 **Members Count:** {member_count}"
        )
        await update.message.reply_text(info_text, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Failed to get group info: {e}")
        await update.message.reply_text(f"❌ Failed to retrieve group info: {e}")


def extract_status_change(chat_member_update) -> tuple[bool, bool] | None:
    """Extracts if a chat member update was a join or a leave."""
    status_change = chat_member_update.difference().get("status")
    if status_change is None:
        return None
    old_status, new_status = status_change

    was_member = old_status in (
        ChatMemberStatus.MEMBER,
        ChatMemberStatus.ADMINISTRATOR,
        ChatMemberStatus.OWNER,
    )
    is_member = new_status in (
        ChatMemberStatus.MEMBER,
        ChatMemberStatus.ADMINISTRATOR,
        ChatMemberStatus.OWNER,
    )

    return was_member, is_member


async def greet_chat_members(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Greets new members when they join the chat and logs leaves."""
    result = extract_status_change(update.chat_member)
    if result is None:
        return

    was_member, is_member = result
    member_name = update.chat_member.new_chat_member.user.first_name

    # Check if a user joined
    if not was_member and is_member:
        await update.effective_chat.send_message(
            f"Welcome {member_name} to the group! 🎉\n"
            f"Please read the /rules and enjoy your stay!"
        )
    # Check if a user left
    elif was_member and not is_member:
        await update.effective_chat.send_message(
            f"{member_name} has left the group. Goodbye! 👋"
        )


async def filter_bad_words(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Checks messages for bad words, deletes them, and warns the sender (exempts admins)."""
    if not update.message or not update.message.text:
        return

    text = update.message.text.lower()
    for word in BAD_WORDS:
        if word in text:
            # Exempt admins from the filter
            if await is_admin(update, context):
                return

            try:
                # Delete the message
                await update.message.delete()
                # Send warning message
                username = update.effective_user.first_name
                await update.effective_chat.send_message(
                    f"⚠️ {username}, your message was removed because it contained forbidden words."
                )
            except Exception as e:
                logger.error(f"Failed to delete bad word message or send warning: {e}")
            break


async def kick_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Kicks a user from the group."""
    if not await check_admin_rights(update, context):
        return

    if not update.message.reply_to_message:
        await update.message.reply_text("❌ Please reply to the message of the user you want to kick.")
        return

    target_user = update.message.reply_to_message.from_user
    chat_id = update.effective_chat.id

    try:
        # Ban then unban to kick them out of the group (allows rejoining via invite link)
        await context.bot.ban_chat_member(chat_id=chat_id, user_id=target_user.id)
        await context.bot.unban_chat_member(chat_id=chat_id, user_id=target_user.id)
        await update.message.reply_text(f"👞 Successfully kicked {target_user.first_name}.")
    except Exception as e:
        logger.error(f"Failed to kick user: {e}")
        await update.message.reply_text(f"❌ Failed to kick user. Error: {e}")


async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Bans a user from the group."""
    if not await check_admin_rights(update, context):
        return

    if not update.message.reply_to_message:
        await update.message.reply_text("❌ Please reply to the message of the user you want to ban.")
        return

    target_user = update.message.reply_to_message.from_user
    chat_id = update.effective_chat.id

    try:
        await context.bot.ban_chat_member(chat_id=chat_id, user_id=target_user.id)
        await update.message.reply_text(f"🚫 Successfully banned {target_user.first_name}.")
    except Exception as e:
        logger.error(f"Failed to ban user: {e}")
        await update.message.reply_text(f"❌ Failed to ban user. Error: {e}")


async def mute_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mutes a user (restricts them from sending messages)."""
    if not await check_admin_rights(update, context):
        return

    if not update.message.reply_to_message:
        await update.message.reply_text("❌ Please reply to the message of the user you want to mute.")
        return

    target_user = update.message.reply_to_message.from_user
    chat_id = update.effective_chat.id

    permissions = ChatPermissions(can_send_messages=False)

    try:
        await context.bot.restrict_chat_member(
            chat_id=chat_id, user_id=target_user.id, permissions=permissions
        )
        await update.message.reply_text(f"🔇 Successfully muted {target_user.first_name}.")
    except Exception as e:
        logger.error(f"Failed to mute user: {e}")
        await update.message.reply_text(f"❌ Failed to mute user. Error: {e}")


async def unmute_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Unmutes a user (allows them to send messages again)."""
    if not await check_admin_rights(update, context):
        return

    if not update.message.reply_to_message:
        await update.message.reply_text("❌ Please reply to the message of the user you want to unmute.")
        return

    target_user = update.message.reply_to_message.from_user
    chat_id = update.effective_chat.id

    # Restore default writing/posting privileges
    permissions = ChatPermissions(
        can_send_messages=True,
        can_send_audios=True,
        can_send_documents=True,
        can_send_photos=True,
        can_send_videos=True,
        can_send_video_notes=True,
        can_send_voice_notes=True,
        can_send_polls=True,
        can_send_other_messages=True,
        can_add_web_page_previews=True,
        can_change_info=True,
        can_invite_users=True,
        can_pin_messages=True,
        can_manage_topics=True,
    )

    try:
        await context.bot.restrict_chat_member(
            chat_id=chat_id, user_id=target_user.id, permissions=permissions
        )
        await update.message.reply_text(f"🔊 Successfully unmuted {target_user.first_name}.")
    except Exception as e:
        logger.error(f"Failed to unmute user: {e}")
        await update.message.reply_text(f"❌ Failed to unmute user. Error: {e}")


async def invite_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generates an invite link for the group."""
    chat = update.effective_chat
    if not chat or chat.type == "private":
        await update.message.reply_text("❌ This command can only be used in groups.")
        return

    try:
        invite_link_obj = await context.bot.create_chat_invite_link(chat_id=chat.id)
        await update.message.reply_text(
            f"🔗 **Group Invite Link:**\n{invite_link_obj.invite_link}\n\n"
            f"Share this link with anyone you want to add to this group!"
        )
    except Exception as e:
        logger.error(f"Failed to create invite link: {e}")
        await update.message.reply_text(f"❌ Failed to generate invite link. Error: {e}")


def main() -> None:
    """Starts the group bot."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token or token == "your_telegram_bot_token_here":
        logger.error("TELEGRAM_BOT_TOKEN is not set or is still the placeholder value in .env.")
        print(
            "Error: TELEGRAM_BOT_TOKEN is not set. Please create a .env file based on .env.example and configure your token.",
            file=sys.stderr,
        )
        sys.exit(1)

    logger.info("Initializing Telegram group bot application...")
    application = Application.builder().token(token).build()

    # Commands
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("rules", rules))
    application.add_handler(CommandHandler("groupinfo", group_info))
    application.add_handler(CommandHandler("invite", invite_link))
    application.add_handler(CommandHandler("kick", kick_user))
    application.add_handler(CommandHandler("ban", ban_user))
    application.add_handler(CommandHandler("mute", mute_user))
    application.add_handler(CommandHandler("unmute", unmute_user))

    # Listen for chat member changes (joins and leaves)
    application.add_handler(ChatMemberHandler(greet_chat_members, ChatMemberHandler.CHAT_MEMBER))

    # Message filter for offensive/spam words
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, filter_bad_words))

    # Run the bot and request chat_member updates
    logger.info("Group bot is starting polling. Press Ctrl+C to stop.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    import asyncio
    asyncio.set_event_loop(asyncio.new_event_loop())
    main()
