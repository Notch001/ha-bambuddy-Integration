"""Minimal async client for the Bambuddy REST API."""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp

from .const import API_PREFIX, REQUEST_TIMEOUT


class BambuddyError(Exception):
    """Base error for the Bambuddy client."""


class BambuddyConnectionError(BambuddyError):
    """Bambuddy could not be reached or answered with an error."""


class BambuddyAuthError(BambuddyError):
    """The API key is missing, invalid or lacks the required permission."""


def normalize_url(url: str) -> str:
    """Return the base URL without trailing slash, defaulting to http://."""
    url = url.strip().rstrip("/")
    if "://" not in url:
        url = f"http://{url}"
    return url


class BambuddyApiClient:
    """Talks to one Bambuddy instance."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        base_url: str,
        api_key: str | None = None,
    ) -> None:
        self._session = session
        self._base_url = normalize_url(base_url)
        self._api_key = api_key or None

    @property
    def base_url(self) -> str:
        return self._base_url

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        headers = {"Accept": "application/json"}
        if self._api_key:
            headers["X-API-Key"] = self._api_key
        url = f"{self._base_url}{API_PREFIX}{path}"
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT.total_seconds()):
                async with self._session.get(
                    url, headers=headers, params=params
                ) as resp:
                    if resp.status in (401, 403):
                        raise BambuddyAuthError(
                            f"Bambuddy rejected the request ({resp.status})"
                        )
                    resp.raise_for_status()
                    return await resp.json()
        except BambuddyError:
            raise
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise BambuddyConnectionError(
                f"Error talking to Bambuddy at {url}: {err}"
            ) from err

    async def get_printers(self) -> list[dict[str, Any]]:
        """Return all printers configured in Bambuddy."""
        return await self._get("/printers/")

    async def get_printer_status(self, printer_id: int) -> dict[str, Any]:
        """Return the live status of one printer."""
        return await self._get(f"/printers/{printer_id}/status")

    async def get_queue(self, status: str | None = None) -> list[dict[str, Any]]:
        """Return queue items, optionally filtered by status."""
        params = {"status": status} if status else None
        return await self._get("/queue/", params=params)
