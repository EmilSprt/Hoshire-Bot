"""Entry point: python main.py"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import discord
from dotenv import load_dotenv

from ticketbot.bot import TicketBot
from ticketbot.config import ConfigError, load_config

BASE_DIR = Path(__file__).parent


def main() -> None:
    load_dotenv(BASE_DIR / ".env")
    discord.utils.setup_logging(level=logging.INFO)

    token = os.getenv("DISCORD_TOKEN")
    if not token or token == "hier_dein_bot_token":
        sys.exit(
            "No bot token found. Copy '.env.example' to '.env' "
            "and enter your token for DISCORD_TOKEN there."
        )

    try:
        config = load_config(BASE_DIR / "config.toml")
    except ConfigError as exc:
        sys.exit(f"Configuration error: {exc}")

    bot = TicketBot(config)
    # log_handler=None: logging was already configured above
    bot.run(token, log_handler=None)


if __name__ == "__main__":
    main()
