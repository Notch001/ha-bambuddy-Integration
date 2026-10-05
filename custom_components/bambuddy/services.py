"""Actions (services) to work with Bambuddy's queue from Home Assistant."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .api import BambuddyError
from .const import DOMAIN
from .coordinator import BambuddyCoordinator
from .entity import raise_for_action

ATTR_DEVICE_ID = "device_id"
ATTR_JOB_ID = "job_id"
ATTR_NAME = "name"
ATTR_ARCHIVE_ID = "archive_id"
ATTR_FILE_ID = "file_id"

DEVICE_SCHEMA = vol.Schema({vol.Required(ATTR_DEVICE_ID): cv.string})
JOB_SCHEMA = vol.Schema({vol.Required(ATTR_JOB_ID): vol.Coerce(int)})
PRINT_AGAIN_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Exclusive(ATTR_NAME, "what"): cv.string,
            vol.Exclusive(ATTR_ARCHIVE_ID, "what"): vol.Coerce(int),
            vol.Optional(ATTR_DEVICE_ID): cv.string,
        }
    ),
    cv.has_at_least_one_key(ATTR_NAME, ATTR_ARCHIVE_ID),
)
PRINT_FILE_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Exclusive(ATTR_NAME, "what"): cv.string,
            vol.Exclusive(ATTR_FILE_ID, "what"): vol.Coerce(int),
            vol.Required(ATTR_DEVICE_ID): cv.string,
        }
    ),
    cv.has_at_least_one_key(ATTR_NAME, ATTR_FILE_ID),
)


def _coordinators(hass: HomeAssistant) -> list[BambuddyCoordinator]:
    return [
        entry.runtime_data
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state is ConfigEntryState.LOADED
    ]


def _error(key: str, **placeholders: Any) -> ServiceValidationError:
    return ServiceValidationError(
        translation_domain=DOMAIN, translation_key=key, translation_placeholders=placeholders
    )


def _printer(hass: HomeAssistant, device_id: str) -> tuple[BambuddyCoordinator, int]:
    device = dr.async_get(hass).async_get(device_id)
    serials = {ident for domain, ident in (device.identifiers if device else ()) if domain == DOMAIN}
    for coordinator in _coordinators(hass):
        for printer_id, printer in coordinator.data.printers.items():
            if printer.get("serial_number") in serials:
                return coordinator, printer_id
    raise _error("printer_not_found")


def _job(hass: HomeAssistant, job_id: int) -> tuple[BambuddyCoordinator, dict[str, Any]]:
    for coordinator in _coordinators(hass):
        for item in coordinator.data.queue:
            if item.get("id") == job_id:
                return coordinator, item
    raise _error("job_not_found", job_id=str(job_id))


def _clean(name: str) -> str:
    name = name.casefold().strip()
    for suffix in (".gcode.3mf", ".3mf", ".gcode"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


def _match(items: list[dict[str, Any]], query: str, *fields: str) -> list[dict[str, Any]]:
    """Exact name matches if there are any, otherwise names containing the query."""
    wanted = _clean(query)
    names = [(item, [_clean(item.get(f) or "") for f in fields]) for item in items]
    exact = [item for item, n in names if wanted in n]
    return exact or [item for item, n in names if any(wanted in x for x in n if x)]


async def _call(action) -> Any:
    try:
        return await action
    except BambuddyError as err:
        raise_for_action(err)


def async_setup_services(hass: HomeAssistant) -> None:
    """Register the actions once for all Bambuddy entries."""

    async def clear_plate(call: ServiceCall) -> None:
        coordinator, printer_id = _printer(hass, call.data[ATTR_DEVICE_ID])
        await _call(coordinator.client.clear_plate(printer_id))
        await coordinator.async_request_refresh()

    async def move_to_front(call: ServiceCall) -> None:
        coordinator, item = _job(hass, call.data[ATTR_JOB_ID])
        await move_job(coordinator, item["id"], None)

    async def cancel(call: ServiceCall) -> None:
        coordinator, item = _job(hass, call.data[ATTR_JOB_ID])
        await _call(coordinator.client.cancel_job(item["id"]))
        await coordinator.async_request_refresh()

    async def start(call: ServiceCall) -> None:
        coordinator, item = _job(hass, call.data[ATTR_JOB_ID])
        await _call(coordinator.client.start_job(item["id"]))
        await coordinator.async_request_refresh()

    async def print_again(call: ServiceCall) -> ServiceResponse:
        if ATTR_DEVICE_ID in call.data:
            coordinators = [_printer(hass, call.data[ATTR_DEVICE_ID])]
        else:
            coordinators = [(c, None) for c in _coordinators(hass)]
        for coordinator, printer_id in coordinators:
            archives = await _call(coordinator.client.list_archives())
            if ATTR_ARCHIVE_ID in call.data:
                found = [a for a in archives if a.get("id") == call.data[ATTR_ARCHIVE_ID]]
            else:
                found = _match(archives, call.data[ATTR_NAME], "print_name", "filename")
            if found:
                archive = found[0]  # newest first
                target = printer_id if printer_id is not None else archive.get("printer_id")
                job = await _call(
                    coordinator.client.add_job(
                        {"archive_id": archive["id"], "printer_id": target, "plate_id": archive.get("plate_id")}
                    )
                )
                await coordinator.async_request_refresh()
                return {"job_id": job.get("id"), "name": archive.get("print_name") or archive.get("filename")}
        raise _error("file_not_found", name=str(call.data.get(ATTR_NAME, call.data.get(ATTR_ARCHIVE_ID))))

    async def print_file(call: ServiceCall) -> ServiceResponse:
        coordinator, printer_id = _printer(hass, call.data[ATTR_DEVICE_ID])
        files = await _call(coordinator.client.list_library_files())
        if ATTR_FILE_ID in call.data:
            found = [f for f in files if f.get("id") == call.data[ATTR_FILE_ID]]
        else:
            found = _match(files, call.data[ATTR_NAME], "filename")
        if not found:
            raise _error("file_not_found", name=str(call.data.get(ATTR_NAME, call.data.get(ATTR_FILE_ID))))
        if len(found) > 1:
            raise _error("file_ambiguous", names=", ".join(f["filename"] for f in found[:5]))
        job = await _call(
            coordinator.client.add_job({"library_file_id": found[0]["id"], "printer_id": printer_id})
        )
        await coordinator.async_request_refresh()
        return {"job_id": job.get("id"), "name": found[0]["filename"]}

    hass.services.async_register(DOMAIN, "clear_plate", clear_plate, DEVICE_SCHEMA)
    hass.services.async_register(DOMAIN, "move_job_to_front", move_to_front, JOB_SCHEMA)
    hass.services.async_register(DOMAIN, "cancel_job", cancel, JOB_SCHEMA)
    hass.services.async_register(DOMAIN, "start_job", start, JOB_SCHEMA)
    hass.services.async_register(
        DOMAIN, "print_again", print_again, PRINT_AGAIN_SCHEMA, supports_response=SupportsResponse.OPTIONAL
    )
    hass.services.async_register(
        DOMAIN, "print_file", print_file, PRINT_FILE_SCHEMA, supports_response=SupportsResponse.OPTIONAL
    )


async def move_job(coordinator: BambuddyCoordinator, job_id: int, after_id: int | None) -> None:
    """Put a waiting job right after another one (None = to the front)."""
    pending = [i["id"] for i in coordinator.data.queue if i.get("status") == "pending"]
    if job_id not in pending:
        raise _error("job_not_movable")
    pending.remove(job_id)
    index = pending.index(after_id) + 1 if after_id in pending else 0
    pending.insert(index, job_id)
    await _call(coordinator.client.reorder_queue([(jid, pos) for pos, jid in enumerate(pending, start=1)]))
    await coordinator.async_request_refresh()
