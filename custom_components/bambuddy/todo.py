"""The print queue as a (read-only) to-do list."""

from __future__ import annotations

from typing import Any

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import BambuddyConfigEntry, BambuddyCoordinator, BambuddyData
from .api import BambuddyError
from .const import DOMAIN
from .entity import BambuddyHubEntity, job_summary, raise_for_action
from .services import move_job

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BambuddyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([BambuddyQueueList(entry.runtime_data)])


def _description(job: dict[str, Any]) -> str:
    parts = [
        job["printer"],
        f"{job['print_time_minutes']} min" if job["print_time_minutes"] else None,
        job["filament_type"],
        f"{round(job['filament_grams'])} g" if job["filament_grams"] else None,
    ]
    text = " · ".join(p for p in parts if p)
    if job.get("estimated_start"):
        start = dt_util.as_local(dt_util.parse_datetime(job["estimated_start"]))
        when = start.strftime("%H:%M")
        if job.get("estimated_end"):
            when += "–" + dt_util.as_local(dt_util.parse_datetime(job["estimated_end"])).strftime("%H:%M")
        if start.date() != dt_util.now().date():
            when = start.strftime("%d.%m. ") + when
        text = f"{text} · ⏱ {when}" if text else f"⏱ {when}"
    if job.get("filament_ok") is False:
        text = f"{text}\n⚠ {', '.join(job['filament_missing'])}"
    if job["waiting_reason"]:
        text = f"{text}\n{job['waiting_reason']}" if text else job["waiting_reason"]
    return text


def _due(job: dict[str, Any]):
    """Only a start time in the future is worth showing as a due date."""
    if not job["scheduled_time"]:
        return None
    due = dt_util.parse_datetime(job["scheduled_time"])
    if due is None or due <= dt_util.utcnow():
        return None
    return due


def _queue_items(data: BambuddyData) -> list[TodoItem]:
    """Running jobs first (marked with ▶), then the waiting ones numbered in order."""
    printing = [job_summary(i, data) for i in data.queue if i.get("status") == "printing"]
    pending = [job_summary(i, data) for i in data.queue if i.get("status") == "pending"]
    items = [
        TodoItem(
            uid=str(job["id"]),
            summary=f"▶ {job['name'] or '?'}",
            status=TodoItemStatus.NEEDS_ACTION,
            description=_description(job) or None,
        )
        for job in printing
    ]
    items += [
        TodoItem(
            uid=str(job["id"]),
            summary=f"{number}. {job['name'] or '?'}",
            status=TodoItemStatus.NEEDS_ACTION,
            description=_description(job) or None,
            due=_due(job),
        )
        for number, job in enumerate(pending, start=1)
    ]
    return items


class BambuddyQueueList(BambuddyHubEntity, TodoListEntity):
    """Shows Bambuddy's queue in the to-do panel and on to-do list cards.

    Waiting jobs can be dragged into a new order and deleted (= cancelled in
    Bambuddy); both need the API key's "queue" permission. Ticking items off
    is not offered: jobs finish by printing.
    """

    _attr_translation_key = "queue"
    _attr_supported_features = (
        TodoListEntityFeature.MOVE_TODO_ITEM | TodoListEntityFeature.DELETE_TODO_ITEM
    )

    def __init__(self, coordinator: BambuddyCoordinator) -> None:
        super().__init__(coordinator, "queue_list")
        self._attr_todo_items = _queue_items(coordinator.data)

    @callback
    def _handle_coordinator_update(self) -> None:
        self._attr_todo_items = _queue_items(self.coordinator.data)
        super()._handle_coordinator_update()

    async def async_move_todo_item(self, uid: str, previous_uid: str | None = None) -> None:
        await move_job(
            self.coordinator, int(uid), int(previous_uid) if previous_uid else None
        )

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        pending = {i["id"] for i in self.coordinator.data.queue if i.get("status") == "pending"}
        for uid in uids:
            if int(uid) not in pending:
                raise ServiceValidationError(
                    translation_domain=DOMAIN, translation_key="job_not_movable"
                )
        for uid in uids:
            try:
                await self.coordinator.client.cancel_job(int(uid))
            except BambuddyError as err:
                raise_for_action(err)
        await self.coordinator.async_request_refresh()
