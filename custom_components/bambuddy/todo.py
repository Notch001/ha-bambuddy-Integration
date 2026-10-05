"""The print queue as a (read-only) to-do list."""

from __future__ import annotations

from typing import Any

from homeassistant.components.todo import TodoItem, TodoItemStatus, TodoListEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import BambuddyConfigEntry, BambuddyCoordinator
from .entity import BambuddyHubEntity, job_summary

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


def _queue_items(queue: list[dict[str, Any]]) -> list[TodoItem]:
    """Running jobs first (marked with ▶), then the waiting ones numbered in order."""
    printing = [job_summary(i) for i in queue if i.get("status") == "printing"]
    pending = [job_summary(i) for i in queue if i.get("status") == "pending"]
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

    No features are supported, so Home Assistant offers no editing: the
    queue is managed in Bambuddy.
    """

    _attr_translation_key = "queue"

    def __init__(self, coordinator: BambuddyCoordinator) -> None:
        super().__init__(coordinator, "queue_list")
        self._attr_todo_items = _queue_items(coordinator.data.queue)

    @callback
    def _handle_coordinator_update(self) -> None:
        self._attr_todo_items = _queue_items(self.coordinator.data.queue)
        super()._handle_coordinator_update()
