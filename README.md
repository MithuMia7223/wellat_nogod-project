# Telegram "Heyo!" Bot

A simple Python Telegram bot that responds with **"Heyo!"** whenever a user sends **"Hi!"** or **"hi"**.

## Prerequisites

- Python 3.8 or higher installed.
- A Telegram account to create a bot and get an API token.

## Setup Instructions

### 1. Create a Bot on Telegram

1. Open Telegram and search for the `@BotFather` username.
2. Start a conversation with `@BotFather` and send the `/newbot` command.
3. Follow the instructions to give your bot a name and a username.
4. BotFather will provide you with an **API Token**. Keep this token secure!

### 2. Configure Environment Variables

1. Copy the template `.env.example` file to a new file named `.env`:
   ```bash
   cp .env.example .env
   ```
2. Open the `.env` file and replace `your_telegram_bot_token_here` with the API Token you obtained from BotFather:
   ```env
   TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ
   ```

### 3. Install Dependencies

It is recommended to run the bot in a virtual environment:

1. Create a virtual environment:
   ```bash
   python3 -m venv venv
   ```
2. Activate the virtual environment:
   * **macOS and Linux:**
     ```bash
     source venv/bin/activate
     ```
   * **Windows (cmd):**
     ```cmd
     venv\Scripts\activate.bat
     ```
   * **Windows (PowerShell):**
     ```powershell
     .\venv\Scripts\Activate.ps1
     ```
3. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Running the Bots

You can run either the simple greeting bot or the group manager bot.

### 1. Simple Heyo! Bot
Run the simple bot:
```bash
python bot.py
```
Go to Telegram, search for your bot's username, start the chat, and type `Hi!` or `hi` to see the bot respond with `Heyo!`.

### 2. Group Manager Bot
Run the group manager bot:
```bash
python group_bot.py
```

#### Setup for Group Bot:
1. Add the bot to your Telegram Group/Supergroup.
2. Promote the bot to **Administrator** and grant permissions (e.g., Ban Users, Delete Messages, Restrict Members).
3. The bot will automatically welcome new members and log when members leave.

#### Available Commands:
* `/rules` - Displays the group rules.
* `/groupinfo` - Displays details about the group (ID, Title, type, and member count).
* `/mute` (replying to a member) - Restricts the member from sending messages.
* `/unmute` (replying to a member) - Lifts message restrictions.
* `/kick` (replying to a member) - Kicks the member from the group.
* `/ban` (replying to a member) - Bans the member from the group.
* **Word Filtering** - Automatically deletes messages containing forbidden words (e.g. `scam`, `cheat`, `spamlink`) and warns the sender (Admins are exempt).

## Running the Tests

To verify the bot logic and message handling rules without sending real Telegram API requests, you can run the included unit tests.

### Test Simple Bot
```bash
python -m unittest test_bot.py
```

### Test Group Bot
```bash
python -m unittest test_group_bot.py
```


