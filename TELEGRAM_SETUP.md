# Telegram Bot Setup Guide

This guide explains how to set up a Telegram bot to automatically post the Signals digest draft to your planning channel each morning.

## Prerequisites

- A Telegram account
- Access to create a Telegram bot via [@BotFather](https://t.me/botfather)
- A Telegram channel or group where you want to post the digest

## Step 1: Create a Telegram Bot

1. Open Telegram and search for [@BotFather](https://t.me/botfather)
2. Start a conversation with BotFather
3. Send the command `/newbot`
4. Follow the prompts:
   - Choose a name for your bot (e.g., "Squid Digest Bot")
   - Choose a username for your bot (must end in `bot`, e.g., `squid_digest_bot`)
5. BotFather will provide you with a **bot token** that looks like:
   ```
   123456789:ABCdefGHIjklMNOpqrsTUVwxyz
   ```
   **Save this token** - you'll need it for GitHub Actions secrets.

## Step 2: Get Your Channel ID

You need to find your channel's ID. There are several methods:

### Method 1: Using @userinfobot (Recommended)

1. Add [@userinfobot](https://t.me/userinfobot) to your channel
2. Send any message in the channel
3. The bot will reply with channel information including the channel ID
4. The channel ID will be a negative number like `-1001234567890`

### Method 2: Using Telegram Web

1. Open [Telegram Web](https://web.telegram.org)
2. Navigate to your channel
3. Look at the URL - it will contain the channel ID
4. For channels, the ID format is usually `-100` followed by numbers

### Method 3: Using the Bot API

1. Add your bot to the channel as an administrator
2. Send a test message to the channel
3. Use this API call to get updates:
   ```
   https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
   ```
4. Look for the `chat` object in the response - the `id` field is your channel ID

**Note**: For channels, the ID is typically a negative number starting with `-100`.

## Step 3: Add Bot to Channel

1. Open your Telegram channel
2. Go to channel settings (tap the channel name at the top)
3. Select "Administrators"
4. Tap "Add Administrator"
5. Search for your bot by username
6. Grant the bot permission to "Post Messages"
7. Save the changes

## Step 4: Configure GitHub Actions Secrets

1. Go to your GitHub repository
2. Navigate to **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Add the following secrets:

   **Secret 1: `TELEGRAM_BOT_TOKEN`**
   - Name: `TELEGRAM_BOT_TOKEN`
   - Value: Your bot token from Step 1 (e.g., `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

   **Secret 2: `TELEGRAM_CHANNEL_ID`**
   - Name: `TELEGRAM_CHANNEL_ID`
   - Value: Your channel ID from Step 2 (e.g., `-1001234567890`)

## Step 5: Test the Integration

1. The Telegram posting step runs automatically after the digest is generated (around 5 AM PT)
2. You can also test manually by:
   - Going to your repository's **Actions** tab
   - Finding the "Generate Daily Digest Draft" workflow
   - Clicking **Run workflow** → **Run workflow**

3. Check your Telegram channel to verify the message was posted

## Troubleshooting

### Bot Not Posting Messages

- **Check bot permissions**: Ensure the bot is an administrator with "Post Messages" permission
- **Verify channel ID**: Make sure you're using the correct channel ID (should be negative for channels)
- **Check bot token**: Verify the token is correct and hasn't been revoked
- **Review workflow logs**: Check the GitHub Actions logs for error messages

### Message Formatting Issues

- Telegram supports limited HTML tags. The formatter automatically converts tables to lists.
- If messages are too long, they will be split into multiple parts automatically.
- Images from the original digest are not included (Telegram text messages don't support inline images).

### Bot Token Security

- **Never commit your bot token to the repository**
- Always use GitHub Secrets for sensitive credentials
- If your token is compromised, revoke it in BotFather (`/revoke`) and create a new one

## Local Testing

To test the Telegram integration locally:

1. Create a `.env` file in the project root (copy from `env.template`)
2. Add your Telegram credentials:
   ```
   TELEGRAM_BOT_TOKEN=your-bot-token
   TELEGRAM_CHANNEL_ID=your-channel-id
   ```
3. Run the formatter and client:
   ```python
   from squid_digest.telegram import TelegramClient, format_for_telegram
   from pathlib import Path
   
   client = TelegramClient()
   signals_path = Path('writeup/signals_2025-11-03.md')  # Use a recent file
   content = signals_path.read_text()
   messages = format_for_telegram(content)
   results = client.send_multiple_messages(messages)
   print(f"Sent {len(results)} message(s)")
   ```

## Additional Resources

- [Telegram Bot API Documentation](https://core.telegram.org/bots/api)
- [Telegram Bot FAQ](https://core.telegram.org/bots/faq)
- [BotFather Commands](https://t.me/botfather)

