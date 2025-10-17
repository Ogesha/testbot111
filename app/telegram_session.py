from __future__ import annotations

from typing import Optional

from aiohttp import ClientTimeout
from aiogram.client.session.aiohttp import AiohttpSession


_DEFAULT_TIMEOUT = ClientTimeout(total=60)


def create_telegram_session(timeout: Optional[ClientTimeout] = None) -> AiohttpSession:
    """Build an aiogram HTTP session that honours proxy-related env vars.

    Aiogram's default session ignores environment proxies which makes it
    impossible to reach Telegram when the host is behind a corporate proxy.
    Enabling ``trust_env`` lets aiohttp reuse the standard ``HTTPS_PROXY`` and
    friends while still allowing callers to override the timeout if needed.
    """

    return AiohttpSession(timeout=timeout or _DEFAULT_TIMEOUT, trust_env=True)
