from __future__ import annotations

import logging
import os
from typing import Optional, Tuple, Union

from aiohttp import BasicAuth, ClientTimeout
from aiogram.client.session.aiohttp import AiohttpSession


logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 60.0
_PROXY_ENV_ORDER = (
    "https_proxy",
    "HTTPS_PROXY",
    "all_proxy",
    "ALL_PROXY",
    "http_proxy",
    "HTTP_PROXY",
)


TimeoutType = Union[float, ClientTimeout]


def _resolve_timeout(timeout: Optional[TimeoutType]) -> float:
    if isinstance(timeout, ClientTimeout):
        # ClientTimeout.total may be None when the instance is created with
        # keyword arguments for connect/read timeouts, so fall back to the
        # module default in that scenario.
        return timeout.total or _DEFAULT_TIMEOUT
    if timeout is not None:
        return float(timeout)
    return _DEFAULT_TIMEOUT


def _proxy_from_env() -> Optional[str]:
    for env_name in _PROXY_ENV_ORDER:
        raw = os.environ.get(env_name)
        if raw:
            return raw.strip()
    return None


def _split_proxy_auth(proxy_url: str) -> Tuple[str, Optional[BasicAuth]]:
    """Extract proxy credentials if they were provided inline."""

    try:
        from urllib.parse import urlsplit, urlunsplit
    except ImportError:  # pragma: no cover - stdlib always available
        return proxy_url, None

    try:
        parts = urlsplit(proxy_url)
    except ValueError:
        return proxy_url, None

    if not parts.username and not parts.password:
        return proxy_url, None

    netloc = parts.hostname or ""
    if parts.port:
        netloc = f"{netloc}:{parts.port}"

    clean_url = urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
    auth = BasicAuth(parts.username or "", parts.password or "")
    return clean_url, auth


def create_telegram_session(timeout: Optional[TimeoutType] = None) -> AiohttpSession:
    """Build an aiogram HTTP session that honours proxy-related env vars."""

    resolved_timeout = _resolve_timeout(timeout)
    proxy_url = _proxy_from_env()

    if proxy_url:
        proxy, auth = _split_proxy_auth(proxy_url)
        proxy_argument: Union[str, Tuple[str, BasicAuth]]
        proxy_argument = (proxy, auth) if auth else proxy

        try:
            return AiohttpSession(proxy=proxy_argument, timeout=resolved_timeout)
        except RuntimeError:
            logger.warning(
                "Proxy support requires the optional aiohttp-socks package; "
                "falling back to a direct Telegram connection.",
                exc_info=True,
            )

    return AiohttpSession(timeout=resolved_timeout)
