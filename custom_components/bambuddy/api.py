"""Minimal async client for the Bambuddy REST API."""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp

from .const import API_PREFIX, CAMERA_TIMEOUT, CAMERA_TOKEN_LIFETIME, REQUEST_TIMEOUT


class BambuddyError(Exception):
    """Base error for the Bambuddy client."""


class BambuddyConnectionError(BambuddyError):
    """Bambuddy could not be reached or answered with an error."""


class BambuddyAuthError(BambuddyError):
    """The API key is missing, invalid or lacks the required permission."""


class BambuddyNotFoundError(BambuddyError):
    """The requested resource does not exist (e.g. no cover image right now)."""


class BambuddyRequestError(BambuddyError):
    """Bambuddy refused the request, e.g. "Printer not connected"."""


async def _error_detail(resp: aiohttp.ClientResponse) -> str:
    try:
        detail = (await resp.json()).get("detail")
    except (aiohttp.ContentTypeError, ValueError, AttributeError):
        detail = None
    if isinstance(detail, dict):
        detail = detail.get("message")
    return str(detail or f"HTTP {resp.status}")


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
        self._camera_token_value: str | None = None
        self._camera_token_expiry = 0.0

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def session(self) -> aiohttp.ClientSession:
        return self._session

    @property
    def headers(self) -> dict[str, str]:
        return {"X-API-Key": self._api_key} if self._api_key else {}

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        *,
        raw: bool = False,
        timeout: float = REQUEST_TIMEOUT.total_seconds(),
    ) -> Any:
        """Send a request; return parsed JSON, or (bytes, content type) if raw."""
        headers = {"Accept": "*/*" if raw else "application/json", **self.headers}
        url = f"{self._base_url}{API_PREFIX}{path}"
        try:
            async with asyncio.timeout(timeout):
                async with self._session.request(
                    method, url, headers=headers, params=params
                ) as resp:
                    if resp.status in (401, 403):
                        raise BambuddyAuthError(
                            f"Bambuddy rejected the request ({resp.status})"
                        )
                    if resp.status == 404:
                        raise BambuddyNotFoundError(f"{url} not found")
                    if resp.status == 400:
                        raise BambuddyRequestError(await _error_detail(resp))
                    resp.raise_for_status()
                    if raw:
                        return await resp.read(), resp.content_type
                    return await resp.json()
        except BambuddyError:
            raise
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise BambuddyConnectionError(
                f"Error talking to Bambuddy at {url}: {err}"
            ) from err

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return await self._request("GET", path, params)

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

    async def get_cover(self, printer_id: int) -> tuple[bytes, str]:
        """Return the preview image of the current print."""
        return await self._request("GET", f"/printers/{printer_id}/cover", raw=True)

    async def _camera_token(self) -> str | None:
        """Token for the camera routes, which do not accept the API key directly.

        Tokens live 60 minutes on the Bambuddy side; we renew after 50.
        """
        if not self._api_key:
            return None
        loop = asyncio.get_running_loop()
        if self._camera_token_value is None or loop.time() > self._camera_token_expiry:
            data = await self._request("POST", "/printers/camera/stream-token")
            self._camera_token_value = data["token"]
            self._camera_token_expiry = loop.time() + CAMERA_TOKEN_LIFETIME.total_seconds()
        return self._camera_token_value

    async def get_camera_snapshot(self, printer_id: int) -> bytes:
        for attempt in range(2):
            token = await self._camera_token()
            try:
                data, _ = await self._request(
                    "GET",
                    f"/printers/{printer_id}/camera/snapshot",
                    {"token": token} if token else None,
                    raw=True,
                    timeout=CAMERA_TIMEOUT.total_seconds(),
                )
            except BambuddyAuthError:
                # Token revoked or expired early (e.g. Bambuddy restarted):
                # fetch a fresh one and try once more.
                self._camera_token_value = None
                if attempt or token is None:
                    raise
            else:
                return data
        raise BambuddyAuthError("unreachable")

    async def camera_stream_url(self, printer_id: int) -> str:
        token = await self._camera_token()
        url = f"{self._base_url}{API_PREFIX}/printers/{printer_id}/camera/stream"
        return f"{url}?token={token}" if token else url

    async def _post(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return await self._request("POST", path, params)

    async def pause(self, printer_id: int) -> None:
        await self._post(f"/printers/{printer_id}/print/pause")

    async def resume(self, printer_id: int) -> None:
        await self._post(f"/printers/{printer_id}/print/resume")

    async def stop(self, printer_id: int) -> None:
        await self._post(f"/printers/{printer_id}/print/stop")

    async def clear_plate(self, printer_id: int) -> None:
        await self._post(f"/printers/{printer_id}/clear-plate")

    async def set_chamber_light(self, printer_id: int, on: bool) -> None:
        await self._post(
            f"/printers/{printer_id}/chamber-light", {"on": "true" if on else "false"}
        )

    async def set_print_speed(self, printer_id: int, mode: int) -> None:
        await self._post(f"/printers/{printer_id}/print-speed", {"mode": mode})
