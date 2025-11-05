# Telegram Integration for Hummingbot

## Overview

The Telegram integration allows you to monitor and control your Hummingbot instance from anywhere using Telegram Messenger. This feature provides real-time notifications about bot events and enables command execution through a secure, authenticated interface.

## Features

- ✅ **Real-time Notifications**: Receive instant updates about order execution, errors, balance changes, and other bot events
- ✅ **Command Execution**: Control your bot remotely with Telegram commands
- ✅ **Secure Authentication**: Only authorized chat IDs can interact with your bot
- ✅ **Rate Limiting**: Built-in protection against API rate limits
- ✅ **Message Queue Management**: Reliable message delivery with automatic retry
- ✅ **Markdown Formatting**: Rich text formatting for better readability
- ✅ **Inline Buttons**: Quick access to common commands via interactive buttons
- ✅ **Error Handling**: Robust error handling with automatic recovery

## Prerequisites

Before setting up Telegram integration, you need:

1. A Telegram account
2. The Telegram app installed on your device (mobile or desktop)
3. Your Hummingbot instance up and running

## Setup Guide

### Step 1: Create a Telegram Bot

1. Open Telegram and search for **@BotFather** or click this link: https://telegram.me/BotFather
2. Start a conversation by clicking **Start** or typing `/start`
3. Create a new bot by typing `/newbot`
4. Follow the prompts:
   - **Bot name**: Give your bot a display name (e.g., "My Hummingbot")
   - **Bot username**: Choose a unique username ending with "bot" (e.g., "my_awesome_hummingbot")
5. **Save the token**: BotFather will provide a token like `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`. **Keep this token secure!**

### Step 2: Get Your Telegram Chat ID

1. Search for **@userinfobot** in Telegram or click this link: https://telegram.me/userinfobot
2. Start a conversation by clicking **Start** or typing `/start`
3. The bot will reply with your user information, including your **Chat ID**
4. **Save your Chat ID** (it will look like: `123456789`)

### Step 3: Start Your Bot

1. Click the link provided by BotFather to open your bot (e.g., `t.me/my_awesome_hummingbot`)
2. Click **Start** to activate the bot

### Step 4: Configure Hummingbot

#### Option 1: Using Configuration Commands

Start Hummingbot and run these commands:

```bash
# Enable Telegram integration
config telegram_enabled

# Enter your bot token (from BotFather)
config telegram_token

# Enter your chat ID (from userinfobot)
config telegram_chat_id

# Optional: Enable autostart (bot starts with Hummingbot)
config telegram_autostart
```

#### Option 2: Manual Configuration

Edit your configuration file at `~/.hummingbot/conf/conf_client.yml`:

```yaml
telegram:
  telegram_enabled: true
  telegram_token: "123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
  telegram_chat_id: "123456789"
  telegram_autostart: false
```

### Step 5: Start the Telegram Integration

In the Hummingbot CLI, run:

```bash
telegram start
```

You should receive a welcome message in your Telegram bot!

## Available Commands

### Bot Commands (via Telegram)

| Command | Description |
|---------|-------------|
| `/start` | Show welcome message and command menu |
| `/help` | Display help information |
| `/status` | Get current bot status |
| `/balance` | Check account balances |
| `/pnl` | View profit and loss |
| `/history` | See recent trade history |
| `/config` | Show current configuration |
| `/startbot` | Start trading strategy |
| `/stopbot` | Stop trading strategy |

### CLI Commands (in Hummingbot)

| Command | Description |
|---------|-------------|
| `telegram start` | Start Telegram integration |
| `telegram stop` | Stop Telegram integration |
| `telegram restart` | Restart Telegram integration |

## Interactive Buttons

The Telegram bot includes interactive inline buttons for quick access to common commands. Simply press the buttons in the Telegram chat to execute commands instantly.

## Security Features

### Authentication

- **Chat ID Verification**: Only messages from your authorized chat ID are processed
- **Unauthorized Access Logging**: All unauthorized access attempts are logged
- **Token Security**: Your bot token is stored securely in Hummingbot's configuration

### Best Practices

1. **Never share your bot token**: Treat it like a password
2. **Never share your chat ID**: This is your authentication key
3. **Use a strong token**: BotFather generates secure tokens automatically
4. **Monitor logs**: Check for unauthorized access attempts
5. **Disable when not needed**: Use `telegram stop` when you don't need remote access

## Rate Limiting

The integration includes built-in rate limiting to comply with Telegram's API limits:

- **Maximum 20 messages per minute**
- **Maximum 3 messages per second**
- **Automatic retry with backoff** for rate limit errors

Messages that exceed rate limits are automatically queued and sent when possible.

## Notifications

The Telegram integration automatically sends notifications for:

- **Bot startup/shutdown**
- **Strategy start/stop events**
- **Order placements and fills**
- **Error messages and warnings**
- **Balance updates**
- **System messages from Hummingbot**

All notifications are formatted with Markdown for better readability.

## Troubleshooting

### Bot doesn't respond to commands

**Problem**: The bot receives your messages but doesn't respond.

**Solutions**:
1. Verify your chat ID is correct: `config telegram_chat_id`
2. Check that Telegram is running: Look for "Telegram notifier connected successfully! 🤖" in logs
3. Restart the integration: `telegram restart`

### "Telegram token is not set" error

**Problem**: Telegram fails to start with token error.

**Solutions**:
1. Configure your token: `config telegram_token`
2. Make sure you copied the entire token from BotFather
3. Check for extra spaces or characters

### Messages are delayed

**Problem**: Messages arrive late or in batches.

**Solutions**:
1. This is likely due to rate limiting - it's normal behavior
2. Reduce notification frequency if possible
3. Check your internet connection

### "Unauthorized access attempt" in logs

**Problem**: Logs show unauthorized access attempts.

**Solutions**:
1. Someone else is trying to use your bot
2. Verify your chat ID is configured correctly
3. If you created a new Telegram account, update your chat ID
4. Consider creating a new bot if you suspect your token was compromised

### Bot stops responding after some time

**Problem**: Bot works initially but stops responding.

**Solutions**:
1. Check Hummingbot is still running
2. Check your internet connection
3. Restart Telegram integration: `telegram restart`
4. Check logs for error messages

### Cannot start Telegram - connection timeout

**Problem**: Telegram fails to start with timeout error.

**Solutions**:
1. Check your internet connection
2. Verify the token is correct
3. Try restarting Hummingbot
4. Check if Telegram's servers are accessible from your network

## Advanced Configuration

### Autostart

To automatically start Telegram when Hummingbot launches:

```bash
config telegram_autostart
# Set to True
```

### Headless Mode

Telegram works seamlessly in headless mode. Configure autostart for full remote control:

```yaml
telegram:
  telegram_enabled: true
  telegram_token: "your_token"
  telegram_chat_id: "your_chat_id"
  telegram_autostart: true
```

Then start Hummingbot in headless mode:

```bash
hummingbot --headless
```

### Multiple Bots

You can control multiple Hummingbot instances with Telegram:

1. **Option A**: Use the same bot with different Hummingbot instances
   - Each instance will use the same chat, so all messages appear together
   - Useful for consolidated monitoring

2. **Option B**: Create separate bots for each instance
   - Create a new bot in BotFather for each Hummingbot instance
   - Each bot will have its own chat
   - Better organization and separation

## API Reference

### TelegramNotifier Class

The `TelegramNotifier` class extends `NotifierBase` and provides:

```python
from hummingbot.notifier.telegram_notifier import TelegramNotifier

# Create notifier
notifier = TelegramNotifier(
    hb_app=hummingbot_app,
    token="your_telegram_token",
    chat_id="your_chat_id"
)

# Start notifier
notifier.start()

# Send message
notifier.add_message_to_queue("Hello from Hummingbot!")

# Stop notifier
notifier.stop()
```

### Configuration Schema

```python
class TelegramConfigMap(BaseClientModel):
    telegram_enabled: bool          # Enable/disable integration
    telegram_token: str             # Bot token from BotFather
    telegram_chat_id: str           # Your Telegram chat ID
    telegram_autostart: bool        # Start with Hummingbot
```

## Architecture

### Components

1. **TelegramNotifier** (`hummingbot/notifier/telegram_notifier.py`)
   - Extends `NotifierBase`
   - Manages Telegram Bot API connection
   - Handles message queuing and rate limiting
   - Processes commands from Telegram

2. **TelegramCommand** (`hummingbot/client/command/telegram_command.py`)
   - Provides CLI commands (start/stop/restart)
   - Manages notifier lifecycle
   - Handles configuration validation

3. **TelegramConfigMap** (`hummingbot/client/config/client_config_map.py`)
   - Configuration data structure
   - Validation and defaults

### Message Flow

```
[Hummingbot] --> [NotifierBase Queue] --> [TelegramNotifier] --> [Telegram API] --> [Your Phone]
[Your Phone] --> [Telegram API] --> [TelegramNotifier] --> [Command Handler] --> [Hummingbot]
```

## Testing

### Run Unit Tests

```bash
pytest test/hummingbot/notifier/test_telegram_notifier.py
```

### Run Integration Tests

```bash
pytest test/hummingbot/client/command/test_telegram_command.py
```

### Manual Testing

1. Configure Telegram with your credentials
2. Start the integration: `telegram start`
3. Send a test notification: `notify This is a test`
4. Try commands in Telegram: `/status`, `/help`, etc.
5. Test inline buttons
6. Stop the integration: `telegram stop`

## FAQ

### Q: Can I use Telegram with multiple Hummingbot instances?

**A**: Yes! You can either use the same bot token with all instances (they'll share one chat), or create separate bots for each instance.

### Q: Does Telegram work in Docker?

**A**: Yes, Telegram works perfectly in Docker containers as long as the container has internet access.

### Q: Can multiple users control one bot?

**A**: No, only one chat ID can be configured per Hummingbot instance for security reasons. However, you can use Telegram's group chat feature (advanced setup required).

### Q: What happens if my internet connection drops?

**A**: The notifier will attempt to reconnect automatically. Queued messages will be sent once the connection is restored.

### Q: How much data does Telegram use?

**A**: Very little - typically a few kilobytes per message. Even with frequent notifications, data usage is minimal.

### Q: Is Telegram integration free?

**A**: Yes! Both Telegram and this integration are completely free to use.

## Support

For issues, questions, or contributions:

- **GitHub Issues**: https://github.com/hummingbot/hummingbot/issues
- **Discord**: https://discord.gg/hummingbot
- **Documentation**: https://docs.hummingbot.org

## Contributing

Contributions are welcome! Please see:

- Issue #7511 for the original bounty requirements
- CONTRIBUTING.md for contribution guidelines

## License

This integration is part of Hummingbot and is licensed under Apache 2.0.

## Changelog

### Version 1.0.0 (2025-11-05)

- ✅ Initial release
- ✅ Real-time notifications
- ✅ Command execution via Telegram
- ✅ Secure authentication
- ✅ Rate limiting
- ✅ Inline buttons
- ✅ Comprehensive error handling
- ✅ Unit and integration tests
- ✅ Full documentation
