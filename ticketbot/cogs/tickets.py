"""Ticket system: button panel, private ticket channels, moderator closing.

No database is intentionally required: the ticket creator is stored in the
channel topic (``ticket-owner:<user_id>``). This allows everything to survive a
bot restart, and open tickets can always be found again.
"""

from __future__ import annotations

import asyncio
import io
import logging
import re
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

if TYPE_CHECKING:
    from ticketbot.bot import TicketBot

log = logging.getLogger(__name__)

# Fixed custom_ids make the buttons persistent (they keep working after restarts).
CREATE_TICKET_ID = "tickets:create"
CLOSE_TICKET_ID = "tickets:close"
TOPIC_PREFIX = "ticket-owner:"


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------
def get_ticket_owner_id(channel: discord.abc.GuildChannel | object) -> int | None:
    """Return the ticket creator's user ID, or None if this is not a ticket."""
    topic = getattr(channel, "topic", None)
    if not topic or not topic.startswith(TOPIC_PREFIX):
        return None
    try:
        return int(topic.removeprefix(TOPIC_PREFIX).split()[0])
    except (ValueError, IndexError):
        return None


def ticket_channel_name(member: discord.Member) -> str:
    slug = re.sub(r"[^a-z0-9_-]", "", member.name.lower())
    return f"ticket-{slug or member.id}"[:100]


def _has_create_button(message: discord.Message) -> bool:
    return any(
        getattr(child, "custom_id", None) == CREATE_TICKET_ID
        for row in message.components
        for child in getattr(row, "children", [])
    )


# ---------------------------------------------------------------------------
# Buttons / Views
# ---------------------------------------------------------------------------
class CreateTicketButton(discord.ui.Button):
    def __init__(self, cog: Tickets) -> None:
        super().__init__(
            label=cog.config.messages.panel_button_label,
            style=discord.ButtonStyle.primary,
            emoji="🎫",
            custom_id=CREATE_TICKET_ID,
        )
        self.cog = cog

    async def callback(self, interaction: discord.Interaction) -> None:
        await self.cog.handle_create(interaction)


class CloseTicketButton(discord.ui.Button):
    def __init__(self, cog: Tickets) -> None:
        super().__init__(
            label=cog.config.messages.close_button_label,
            style=discord.ButtonStyle.danger,
            emoji="🔒",
            custom_id=CLOSE_TICKET_ID,
        )
        self.cog = cog

    async def callback(self, interaction: discord.Interaction) -> None:
        await self.cog.handle_close(interaction)


class TicketPanelView(discord.ui.View):
    """The message in the panel channel with the 'Create ticket' button."""

    def __init__(self, cog: Tickets) -> None:
        super().__init__(timeout=None)
        self.add_item(CreateTicketButton(cog))


class TicketControlView(discord.ui.View):
    """The controls inside a ticket ('Close ticket')."""

    def __init__(self, cog: Tickets) -> None:
        super().__init__(timeout=None)
        self.add_item(CloseTicketButton(cog))


# ---------------------------------------------------------------------------
# Cog
# ---------------------------------------------------------------------------
class Tickets(commands.Cog):
    def __init__(self, bot: TicketBot) -> None:
        self.bot = bot
        self.config = bot.config
        self._closing: set[int] = set()  # Channel IDs currently being closed
        self._creating: set[int] = set()  # User IDs currently creating a ticket

    async def cog_load(self) -> None:
        # Register persistent views so buttons on old messages keep working
        # after a bot restart.
        self.bot.add_view(TicketPanelView(self))
        self.bot.add_view(TicketControlView(self))

    # ----- Permissions ------------------------------------------------------
    def is_moderator(self, member: discord.abc.User) -> bool:
        return isinstance(member, discord.Member) and any(
            role.id == self.config.moderator_role_id for role in member.roles
        )

    # ----- Panel ------------------------------------------------------------
    def _get_panel_channel(self) -> discord.TextChannel | None:
        guild = self.bot.get_guild(self.config.guild_id)
        if guild is None:
            log.error(
                "The bot is not on the server with ID %s. "
                "Check guild_id in config.toml and invite the bot.",
                self.config.guild_id,
            )
            return None
        channel = guild.get_channel(self.config.panel_channel_id)
        if not isinstance(channel, discord.TextChannel):
            log.error(
                "panel_channel_id %s is not a text channel on the server.",
                self.config.panel_channel_id,
            )
            return None
        return channel

    async def _find_panel_messages(
        self, channel: discord.TextChannel
    ) -> list[discord.Message]:
        assert self.bot.user is not None
        found = []
        async for message in channel.history(limit=100):
            if message.author.id == self.bot.user.id and _has_create_button(message):
                found.append(message)
        return found

    async def send_panel(self, channel: discord.TextChannel) -> None:
        messages = self.config.messages
        embed = discord.Embed(
            title=messages.panel_title,
            description=messages.panel_description,
            colour=discord.Colour.blurple(),
        )
        await channel.send(embed=embed, view=TicketPanelView(self))

    async def ensure_panel(self) -> None:
        """Send the panel if it does not already exist in the panel channel."""
        channel = self._get_panel_channel()
        if channel is None:
            return
        if await self._find_panel_messages(channel):
            log.info("Ticket panel already exists in #%s.", channel.name)
            return
        await self.send_panel(channel)
        log.info("Ticket panel sent to #%s.", channel.name)

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        try:
            await self.ensure_panel()
        except discord.HTTPException:
            log.exception(
                "Could not send panel. Does the bot have the 'View Channel', "
                "'Send Messages', 'Embed Links', and 'Read Message History' "
                "permissions in the panel channel?"
            )

    # ----- Create ticket ----------------------------------------------------
    async def handle_create(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        member = interaction.user
        if guild is None or not isinstance(member, discord.Member):
            await interaction.response.send_message(
                "Tickets can only be created on a server.", ephemeral=True
            )
            return

        if member.id in self._creating:
            await interaction.response.send_message(
                "Your ticket is already being created ...", ephemeral=True
            )
            return

        self._creating.add(member.id)
        try:
            await interaction.response.defer(ephemeral=True, thinking=True)
            await self._create_ticket(interaction, guild, member)
        finally:
            self._creating.discard(member.id)

    async def _create_ticket(
        self,
        interaction: discord.Interaction,
        guild: discord.Guild,
        member: discord.Member,
    ) -> None:
        config = self.config

        mod_role = guild.get_role(config.moderator_role_id)
        if mod_role is None:
            log.error(
                "moderator_role_id %s does not exist on the server.",
                config.moderator_role_id,
            )
            await interaction.followup.send(
                "❌ The bot is configured incorrectly (moderator role not found). "
                "Please notify an administrator.",
                ephemeral=True,
            )
            return

        # Check the per-user open ticket limit.
        open_tickets = [
            c for c in guild.text_channels if get_ticket_owner_id(c) == member.id
        ]
        if len(open_tickets) >= config.max_open_per_user:
            mentions = ", ".join(c.mention for c in open_tickets)
            await interaction.followup.send(
                f"You already have an open ticket: {mentions}", ephemeral=True
            )
            return

        category = None
        if config.ticket_category_id:
            candidate = guild.get_channel(config.ticket_category_id)
            if isinstance(candidate, discord.CategoryChannel):
                category = candidate
            else:
                log.warning(
                    "ticket_category_id %s is not a category; creating the ticket without a category.",
                    config.ticket_category_id,
                )

        user_perms = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            attach_files=True,
            embed_links=True,
        )
        mod_perms = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            attach_files=True,
            embed_links=True,
            manage_messages=True,
        )
        bot_perms = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            embed_links=True,
            attach_files=True,
            manage_channels=True,
        )
        overwrites: dict[discord.Role | discord.Member, discord.PermissionOverwrite] = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: user_perms,
            mod_role: mod_perms,
            guild.me: bot_perms,
        }

        try:
            channel = await guild.create_text_channel(
                name=ticket_channel_name(member),
                category=category,
                overwrites=overwrites,
                topic=f"{TOPIC_PREFIX}{member.id} | Ticket by {member}",
                reason=f"Ticket created by {member} ({member.id})",
            )
        except discord.Forbidden:
            log.exception("Missing permissions to create the ticket channel.")
            await interaction.followup.send(
                "❌ The bot lacks permission to create the ticket channel. "
                "Please notify an administrator.",
                ephemeral=True,
            )
            return
        except discord.HTTPException:
            log.exception("Could not create the ticket channel.")
            await interaction.followup.send(
                "❌ The ticket could not be created. Please try again later.",
                ephemeral=True,
            )
            return

        messages = config.messages
        welcome = discord.Embed(
            title=messages.welcome_title,
            description=messages.welcome_description.replace("{user}", member.mention),
            colour=discord.Colour.green(),
        )
        await channel.send(
            content=f"{member.mention} {mod_role.mention}",
            embed=welcome,
            view=TicketControlView(self),
            allowed_mentions=discord.AllowedMentions(users=[member], roles=[mod_role]),
        )

        log.info("Ticket #%s created for %s (%s).", channel.name, member, member.id)
        await interaction.followup.send(
            f"✅ Your ticket was created: {channel.mention}", ephemeral=True
        )

    # ----- Close ticket -----------------------------------------------------
    async def handle_close(self, interaction: discord.Interaction) -> None:
        channel = interaction.channel
        member = interaction.user

        if (
            not isinstance(channel, discord.TextChannel)
            or get_ticket_owner_id(channel) is None
        ):
            await interaction.response.send_message(
                "This can only be done inside a ticket.", ephemeral=True
            )
            return

        if not self.is_moderator(member):
            await interaction.response.send_message(
                "❌ Only moderators can close tickets.", ephemeral=True
            )
            return

        if channel.id in self._closing:
            await interaction.response.send_message(
                "This ticket is already being closed.", ephemeral=True
            )
            return

        self._closing.add(channel.id)
        delay = self.config.close_delay_seconds
        try:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description=(
                        f"🔒 {member.mention} closed the ticket. "
                        f"This channel will be deleted in {delay} seconds."
                    ),
                    colour=discord.Colour.red(),
                )
            )
            await asyncio.sleep(delay)
            await self._send_log(channel, member)
            await channel.delete(reason=f"Ticket closed by {member} ({member.id})")
            log.info("Ticket #%s closed by %s (%s).", channel.name, member, member.id)
        except discord.HTTPException:
            log.exception("Could not close ticket #%s.", channel.name)
        finally:
            self._closing.discard(channel.id)

    async def _send_log(
        self, channel: discord.TextChannel, closed_by: discord.abc.User
    ) -> None:
        """Write a log entry, optionally with a transcript; errors do not stop closing."""
        if not self.config.log_channel_id:
            return
        log_channel = self.bot.get_channel(self.config.log_channel_id)
        if not isinstance(log_channel, discord.abc.Messageable):
            log.warning("log_channel_id %s was not found.", self.config.log_channel_id)
            return

        owner_id = get_ticket_owner_id(channel)
        embed = discord.Embed(
            title="Ticket closed",
            colour=discord.Colour.red(),
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="Ticket", value=f"#{channel.name}")
        embed.add_field(
            name="Created by", value=f"<@{owner_id}>" if owner_id else "unknown"
        )
        embed.add_field(name="Closed by", value=closed_by.mention)

        try:
            transcript = (
                await self._build_transcript(channel)
                if self.config.transcripts_enabled
                else None
            )
            await log_channel.send(
                embed=embed,
                file=transcript,  # type: ignore[arg-type]
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except discord.HTTPException:
            log.exception("Could not send log entry.")

    @staticmethod
    async def _build_transcript(channel: discord.TextChannel) -> discord.File:
        lines = []
        async for message in channel.history(limit=None, oldest_first=True):
            timestamp = message.created_at.strftime("%Y-%m-%d %H:%M:%S")
            attachments = " ".join(a.url for a in message.attachments)
            line = f"[{timestamp}] {message.author} ({message.author.id}): {message.clean_content} {attachments}"
            lines.append(line.rstrip())
        data = "\n".join(lines).encode("utf-8")
        return discord.File(io.BytesIO(data), filename=f"{channel.name}.txt")

    # ----- Slash commands ---------------------------------------------------
    @app_commands.command(
        name="close", description="Close the current ticket (moderators only)."
    )
    @app_commands.guild_only()
    async def close_command(self, interaction: discord.Interaction) -> None:
        await self.handle_close(interaction)

    @app_commands.command(
        name="ticketpanel",
        description="Resend the ticket panel to the configured channel (administrators only).",
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def panel_command(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        channel = self._get_panel_channel()
        if channel is None:
            await interaction.followup.send(
                "❌ Panel channel not found; see the bot log.", ephemeral=True
            )
            return
        for old in await self._find_panel_messages(channel):
            await old.delete()
        await self.send_panel(channel)
        await interaction.followup.send(
            f"✅ Panel sent to {channel.mention}.", ephemeral=True
        )

    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        if isinstance(error, app_commands.MissingPermissions):
            message = "❌ You do not have the required permissions."
        else:
            log.error("Error in slash command", exc_info=error)
            message = "❌ An unexpected error occurred."
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)


async def setup(bot: TicketBot) -> None:
    await bot.add_cog(Tickets(bot))
