# 🎫 Discord Ticket-Bot

A ticket system for Discord, written in Python with [discord.py](https://discordpy.readthedocs.io/).

## Features

- The bot posts a message with a **"Create ticket"** button in a configured channel.
- Clicking it creates a **private channel** visible only to the ticket creator and the **moderator role**.
- Users and moderators can write in this channel.
- Members with the moderator role can close the ticket using the **"Close ticket"** button (or `/close`). The channel is then deleted.
- Optional log channel and chat transcript when closing.
- All IDs and text are configured in a **configuration file** (`config.toml`).
- Buttons continue to work **after a bot restart**. No database is required.
- **Extensible:** Every new `.py` file in `ticketbot/cogs/` is automatically loaded as an extension (see [Extending the bot](#-extending-the-bot)).

---

## Project structure

```
discord-ticket-bot/
├── main.py                  # Bot entry point
├── config.toml.example      # Configuration template
├── .env.example             # Bot token template
├── requirements.txt         # Python dependencies
├── README.md
└── ticketbot/
    ├── bot.py               # Bot class, automatically loads cogs
    ├── config.py            # Loads and validates config.toml
    └── cogs/
        └── tickets.py       # Ticket system
```

---

## Installation

### 1. Prerequisites

- **Python 3.11 or newer** (check the version with `python --version`, or `python3 --version` on Linux/macOS if needed).
  Download: <https://www.python.org/downloads/>
  _Windows:_ Be sure to check **"Add python.exe to PATH"** during installation.
- A Discord server where you have administrator permissions.

### 2. Create a bot in the Discord Developer Portal

1. Open <https://discord.com/developers/applications> and click **New Application**. Give it a name.
2. Select **Bot** from the menu on the left.
3. Click **Reset Token** -> **Copy**. This is your **bot token**. Keep it temporarily; you will add it to `.env` later.
   > ⚠️ The token is like a password. Never share it or upload it anywhere. If it becomes public, reset it immediately.
4. On the Bot page, scroll to **Privileged Gateway Intents**:
   - You do not need to enable **anything** for standard operation.
   - Enable **Message Content Intent** only if you want to use **transcripts** (`transcripts_enabled = true`).

### 3. Invite the bot to your server

1. In the Developer Portal, go to **OAuth2 -> URL Generator**.
2. Select `bot` and `applications.commands` under **Scopes**.
3. Select the following under **Bot Permissions**:
   - View Channels
   - Manage Channels
   - Manage Roles - required for the bot to set ticket channel permissions
   - Send Messages
   - Embed Links
   - Attach Files
   - Read Message History
4. Copy the generated URL at the bottom, open it in your browser, and add the bot to your server.

### 4. Find the IDs

1. Enable **Developer Mode** in Discord:
   _User Settings -> Advanced -> Developer Mode_.
2. You can now copy the required IDs by right-clicking -> **"Copy ID"**:

| What                 | Where to click                                                                                                                 |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `guild_id`           | Right-click the **server name** / server icon                                                                                  |
| `panel_channel_id`   | Right-click the **channel** where the button should appear                                                                     |
| `moderator_role_id`  | _Server Settings -> Roles_ -> right-click the moderator role (or right-click the role in the member list if it is shown there) |
| `ticket_category_id` | Right-click the **category** where tickets should be created (optional)                                                        |
| `log_channel_id`     | Right-click the **log channel** (optional)                                                                                     |

### 5. Set up the project

Open a terminal in the project directory (`discord-ticket-bot`) and run the following steps.

**a) Create and activate a virtual environment**

Windows (PowerShell):

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Windows (CMD):

```bat
python -m venv .venv
.venv\Scripts\activate.bat
```

Linux / macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

When the environment is active, `(.venv)` appears before your prompt.

**b) Install dependencies**

```bash
pip install -r requirements.txt
```

**c) Add the token**

Copy `.env.example` to `.env`:

```bash
# Linux / macOS
cp .env.example .env
# Windows (CMD)
copy .env.example .env
```

Open `.env` and replace `hier_dein_bot_token` with your token:

```
DISCORD_TOKEN=MTIzNDU2...your_real_token
```

**d) Create the configuration**

Copy `config.toml.example` to `config.toml`:

```bash
# Linux / macOS
cp config.toml.example config.toml
# Windows (CMD)
copy config.toml.example config.toml
```

Open `config.toml` and enter at least these values:

```toml
[discord]
guild_id = 123456789012345678
panel_channel_id = 123456789012345678
moderator_role_id = 123456789012345678
```

### 6. Start the bot

```bash
python main.py
```

(On Linux/macOS, use `python3 main.py` if needed.)

You should see something similar to the following in the terminal:

```
Loaded cog: ticketbot.cogs.tickets
1 slash command(s) synchronized.   (or 2)
Logged in as YourBot#1234 (ID: ...)
Ticket panel sent to #support.
```

The message with the button now appears in the panel channel. Stop the bot with `Ctrl + C`.

> For subsequent starts, you only need to activate the virtual environment (step 5a) and run `python main.py`.

---

## Configuration (`config.toml`)

The bot must be **restarted** after every change to `config.toml`.

### `[discord]`

| Key                  | Required | Description                                         |
| -------------------- | -------- | --------------------------------------------------- |
| `guild_id`           | ✅       | Your server ID                                      |
| `panel_channel_id`   | ✅       | Channel containing the message with the button      |
| `moderator_role_id`  | ✅       | Role allowed to see and close all tickets           |
| `ticket_category_id` | ❌       | Category for new ticket channels (`0` = none)       |
| `log_channel_id`     | ❌       | Channel for log entries when closing (`0` = no log) |

### `[tickets]`

| Key                   | Default | Description                                                                                              |
| --------------------- | ------- | -------------------------------------------------------------------------------------------------------- |
| `max_open_per_user`   | `1`     | Maximum number of open tickets per user at once                                                          |
| `close_delay_seconds` | `5`     | Delay before deleting the channel after closing                                                          |
| `transcripts_enabled` | `false` | Sends a `.txt` transcript to the log channel when closing (requires _Message Content Intent_, see above) |

### `[messages]`

All text (panel title, button labels, and welcome message) can be customized. In `welcome_description`, `{user}` is replaced with the ticket creator's mention.

---

## Usage

| Action        | Who                 | How                                                        |
| ------------- | ------------------- | ---------------------------------------------------------- |
| Create ticket | All members         | **"Create ticket"** button in the panel channel            |
| Close ticket  | Moderator role only | **"Close ticket"** button in the ticket or `/close`        |
| Resend panel  | Administrators only | `/ticketpanel` (deletes the old panel and sends a new one) |

**Notes:**

- At startup, the bot checks whether the panel already exists in the channel. A new message is sent only if it is missing.
- Whether a channel is a ticket and who owns it is stored in the **channel topic** (`ticket-owner:<ID>`). Do not change or delete this topic, or the bot will no longer recognize the ticket.
- Administrators must also have the moderator role to close tickets through the bot.
- The log channel should only be visible to moderators because transcripts contain private conversations.

---

## 🧩 Extending the bot

At startup, the bot **automatically loads every `.py` file** from `ticketbot/cogs/`. Files whose names start with `_` are ignored. This lets you add new features without changing existing code.

**Example:** Create the file `ticketbot/cogs/hello.py`:

```python
import discord
from discord import app_commands
from discord.ext import commands


class Hello(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="hello", description="Says hello.")
    async def hello(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"Hello {interaction.user.mention}!")


async def setup(bot):
    await bot.add_cog(Hello(bot))
```

After a restart, the `/hello` command is available.

**Useful for custom cogs:**

- `self.bot.config` contains the loaded configuration (e.g. `self.bot.config.guild_id`).
- You can add custom settings in a separate section of `config.toml`, such as `[welcome]`, and read them in your cog with `self.bot.config.raw.get("welcome", {})`.
- New slash commands are automatically synchronized to your server at startup.

---

## Troubleshooting

| Problem                                                 | Solution                                                                                                                                                                                                                           |
| ------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `No bot token found`                                    | `.env` is missing or `DISCORD_TOKEN` was not entered (step 5c).                                                                                                                                                                    |
| `Configuration error: … not set`                        | A required field in `config.toml` is still set to `0` (step 5d).                                                                                                                                                                   |
| `Improper token has been passed` / `LoginFailure`       | The token is incorrect or was reset. Generate a new token and add it to `.env`.                                                                                                                                                    |
| `PrivilegedIntentsRequired`                             | `transcripts_enabled = true`, but _Message Content Intent_ is not enabled in the Developer Portal. Enable it or set `transcripts_enabled = false`.                                                                                 |
| No panel in the channel                                 | Check the terminal log. Usually `panel_channel_id` is incorrect, or the bot lacks permission to view, write, and read message history in the channel.                                                                              |
| "The bot lacks permission to create the ticket channel" | Check that the bot has _Manage Channels_ and _Manage Roles_ permissions. The bot role should be **above** the moderator role in the role list. If a category is configured, the bot must also be allowed to manage channels there. |
| Slash commands (`/close`, `/ticketpanel`) do not appear | The bot was invited without the `applications.commands` scope. Invite it again using the URL from step 3.                                                                                                                          |
| Button does not respond ("Interaction failed")          | The bot is not running. Restart it.                                                                                                                                                                                                |

---

## Running continuously (optional)

The bot is online only while `python main.py` is running. For continuous operation on a server (e.g. a Linux VPS), you can configure it as a `systemd` service, for example at `/etc/systemd/system/ticketbot.service`:

```ini
[Unit]
Description=Discord Ticket-Bot
After=network-online.target

[Service]
WorkingDirectory=/path/to/discord-ticket-bot
ExecStart=/path/to/discord-ticket-bot/.venv/bin/python main.py
Restart=on-failure
User=youruser

[Install]
WantedBy=multi-user.target
```

Enable and start it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now ticketbot
```

View logs: `journalctl -u ticketbot -f`
