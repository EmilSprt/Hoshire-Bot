"""Load and validate config.toml."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any


class ConfigError(Exception):
    """Raised when the configuration is missing or invalid."""


@dataclass(frozen=True)
class Messages:
    """All text displayed by the bot (in config.toml under [messages])."""

    panel_title: str = "🎫 Support-Tickets"
    panel_description: str = (
        "Do you need help or have a request?\n"
        "Click the button to create a private ticket."
    )
    panel_button_label: str = "Create ticket"
    welcome_title: str = "Welcome to your ticket"
    welcome_description: str = (
        "Hello {user}, please describe your request in as much detail as possible.\n"
        "A moderator will be with you shortly."
    )
    close_button_label: str = "Close ticket"


@dataclass(frozen=True)
class Config:
    guild_id: int
    panel_channel_id: int
    moderator_role_id: int
    ticket_category_id: int | None
    log_channel_id: int | None
    max_open_per_user: int
    close_delay_seconds: int
    transcripts_enabled: bool
    messages: Messages
    # The complete, unchanged TOML structure. Future extensions (cogs) can
    # read their own sections here, e.g. bot.config.raw.get("my_cog", {}).
    raw: dict[str, Any] = field(default_factory=dict)


def _read_id(section: dict[str, Any], key: str, *, required: bool) -> int | None:
    value = section.get(key, 0)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ConfigError(
            f"[discord] {key} must be a number (Discord ID), but is: {value!r}"
        )
    if value == 0:
        if required:
            raise ConfigError(f"[discord] {key} is not set. Add it to config.toml.")
        return None
    return value


def _read_int(section: dict[str, Any], key: str, default: int, minimum: int) -> int:
    value = section.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ConfigError(
            f"[tickets] {key} must be a number >= {minimum}, but is: {value!r}"
        )
    return value


def load_config(path: Path) -> Config:
    """Read the TOML file and return a validated Config object."""
    if not path.exists():
        raise ConfigError(
            f"Configuration file not found: {path}\n"
            "Copy 'config.toml.example' to 'config.toml' and enter your IDs."
        )

    try:
        with path.open("rb") as file:
            raw = tomllib.load(file)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"config.toml contains a syntax error: {exc}") from exc

    discord_section = raw.get("discord", {})
    tickets_section = raw.get("tickets", {})
    messages_section = raw.get("messages", {})

    known_message_keys = {f.name for f in fields(Messages)}
    messages = Messages(
        **{k: str(v) for k, v in messages_section.items() if k in known_message_keys}
    )

    transcripts_enabled = tickets_section.get("transcripts_enabled", False)
    if not isinstance(transcripts_enabled, bool):
        raise ConfigError("[tickets] transcripts_enabled must be true or false.")

    return Config(
        guild_id=_read_id(discord_section, "guild_id", required=True),  # type: ignore[arg-type]
        panel_channel_id=_read_id(discord_section, "panel_channel_id", required=True),  # type: ignore[arg-type]
        moderator_role_id=_read_id(discord_section, "moderator_role_id", required=True),  # type: ignore[arg-type]
        ticket_category_id=_read_id(
            discord_section, "ticket_category_id", required=False
        ),
        log_channel_id=_read_id(discord_section, "log_channel_id", required=False),
        max_open_per_user=_read_int(tickets_section, "max_open_per_user", 1, 1),
        close_delay_seconds=_read_int(tickets_section, "close_delay_seconds", 5, 0),
        transcripts_enabled=transcripts_enabled,
        messages=messages,
        raw=raw,
    )
