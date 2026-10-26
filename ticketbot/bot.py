"""The bot class: automatically loads all cogs from ticketbot/cogs/."""

from __future__ import annotations

import logging
from pathlib import Path

import discord
from discord.ext import commands

from ticketbot.config import Config

log = logging.getLogger(__name__)

COGS_DIR = Path(__file__).parent / "cogs"


class TicketBot(commands.Bot):
    def __init__(self, config: Config) -> None:
        intents = discord.Intents.default()
        # Only needed when transcripts are enabled (privileged intent).
        intents.message_content = config.transcripts_enabled

        super().__init__(command_prefix=commands.when_mentioned, intents=intents)
        self.config = config

    async def setup_hook(self) -> None:
        await self._load_cogs()

        # Synchronize slash commands only for the configured server.
        # This is immediate; global commands can take up to an hour.
        guild = discord.Object(id=self.config.guild_id)
        self.tree.copy_global_to(guild=guild)
        synced = await self.tree.sync(guild=guild)
        log.info("%d slash command(s) synchronized.", len(synced))

    async def _load_cogs(self) -> None:
        """Load every .py file in ticketbot/cogs/ except files starting with '_'."""
        for path in sorted(COGS_DIR.glob("*.py")):
            if path.name.startswith("_"):
                continue
            extension = f"ticketbot.cogs.{path.stem}"
            await self.load_extension(extension)
            log.info("Loaded cog: %s", extension)

    async def on_ready(self) -> None:
        assert self.user is not None
        log.info("Logged in as %s (ID: %s)", self.user, self.user.id)
