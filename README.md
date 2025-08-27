# 🏰 DungeonKeeper Discord Bot

A comprehensive Discord bot designed for study communities and educational servers with staff support, voice channel management, and productivity features.

## ✨ Features

### 🛠️ Staff Support System
- **DM Bridge**: Automatic forwarding of user DMs to staff channel
- **Interactive Support**: Users get instructions and proceed button before submitting
- **Case Management**: Threaded discussions with unique case IDs
- **Staff Commands**: `/reply` and `/close` commands for case handling

### 🎙️ Voice Channel Management
- `/forcemute` - Mute all members in current voice channel
- `/private` - Lock voice channel to current members only
- `/public` - Unlock voice channel for everyone
- `/max` - Set member limit (0-99)
- `/desc` - Set channel description/topic
- `/invite` - Send DM invite to specific users

### 📚 Study & Productivity Features
- `/topic` - Random conversation starters and discussion questions
- `/studyquote` - Motivational study quotes
- `/pomodoro` - Customizable focus/break timer with XP rewards
- `/rank` - XP leaderboard for study champions
- `/remindme` - Personal reminder system (up to 1 week)

## 🚀 Setup & Deployment

### Prerequisites
- Python 3.8 or higher
- Discord bot token
- Discord server with appropriate permissions

### Local Development

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/dungeonkeeper-bot.git
   cd dungeonkeeper-bot
   ```

2. **Install dependencies:**
   ```bash
   pip install discord.py python-dotenv
   ```

3. **Set up environment variables:**
   Create a `.env` file in the root directory:
   ```env
   DISCORD_TOKEN=your_bot_token_here
   STAFF_CHANNEL_ID=your_staff_channel_id_here
   ```

4. **Run the bot:**
   ```bash
   python main.py
   ```

### Deployment Options

#### Option 1: Heroku
1. Create a `Procfile`:
   ```
   worker: python main.py
   ```

2. Set environment variables in Heroku dashboard or CLI:
   ```bash
   heroku config:set DISCORD_TOKEN=your_token_here
   heroku config:set STAFF_CHANNEL_ID=your_channel_id_here
   ```

#### Option 2: Railway
1. Connect your GitHub repository to Railway
2. Set environment variables in Railway dashboard
3. Deploy automatically on push

#### Option 3: VPS/Cloud Server
1. Clone repository on your server
2. Install Python and dependencies
3. Set up environment variables
4. Use a process manager like `pm2` or `systemd`:

   **Using PM2:**
   ```bash
   npm install -g pm2
   pm2 start main.py --name dungeonkeeper --interpreter python3
   ```

   **Using systemd (create `/etc/systemd/system/dungeonkeeper.service`):**
   ```ini
   [Unit]
   Description=DungeonKeeper Discord Bot
   After=network.target

   [Service]
   Type=simple
   User=your_user
   WorkingDirectory=/path/to/your/bot
   Environment=DISCORD_TOKEN=your_token_here
   Environment=STAFF_CHANNEL_ID=your_channel_id_here
   ExecStart=/usr/bin/python3 main.py
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```

### Bot Permissions Required

When inviting the bot to your server, ensure it has these permissions:
- Send Messages
- Use Slash Commands
- Manage Channels (for voice commands)
- Mute Members (for forcemute)
- Create Instant Invite
- Read Message History
- Send Messages in Threads

### Getting Bot Token

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application or select existing one
3. Go to "Bot" section
4. Copy the token (keep this secret!)
5. Enable required intents:
   - Message Content Intent
   - Server Members Intent (if needed)

### Getting Staff Channel ID

1. Enable Developer Mode in Discord (User Settings > Advanced > Developer Mode)
2. Right-click on your staff channel
3. Click "Copy Channel ID"

## 📊 Bot Statistics
- **14 Slash Commands** - All interactions use modern Discord slash commands
- **XP System** - Gamified productivity tracking
- **Case Management** - Professional support ticket system
- **Multi-Modal Support** - Text, embeds, buttons, and file attachments

## 🛡️ Security Notes
- Never commit your bot token to version control
- Use environment variables for all sensitive data
- Regularly rotate your bot token if compromised
- Monitor bot permissions and access

## 📝 Configuration

The bot uses `config.json` for settings:
```json
{
    "staff_channel_id": 0,
    "bot_settings": {
        "command_prefix": "!",
        "max_reminder_time": 10080,
        "max_pomodoro_focus": 120,
        "max_pomodoro_break": 60,
        "xp_per_pomodoro": 10
    }
}
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

If you need help with the bot:
1. Check the documentation above
2. Create an issue on GitHub
3. Join our support Discord server

---

Built with ❤️ for Discord communities focused on learning and productivity.