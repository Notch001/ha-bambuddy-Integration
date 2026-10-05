"""Names and pictures for filament colours."""

from __future__ import annotations

import base64
from typing import Any

# Fallback when Bambuddy's catalogue has no name for a colour: the nearest of a
# few basic colours, so a slot still reads "PLA · Rot" instead of a hex code.
_BASIC_COLORS: tuple[tuple[tuple[int, int, int], str, str], ...] = (
    ((0, 0, 0), "Schwarz", "Black"),
    ((255, 255, 255), "Weiß", "White"),
    ((128, 128, 128), "Grau", "Gray"),
    ((192, 192, 192), "Silber", "Silver"),
    ((220, 30, 30), "Rot", "Red"),
    ((128, 0, 32), "Bordeaux", "Burgundy"),
    ((255, 140, 0), "Orange", "Orange"),
    ((255, 215, 0), "Gelb", "Yellow"),
    ((210, 180, 140), "Beige", "Beige"),
    ((139, 69, 19), "Braun", "Brown"),
    ((0, 160, 60), "Grün", "Green"),
    ((128, 128, 0), "Oliv", "Olive"),
    ((0, 200, 200), "Türkis", "Turquoise"),
    ((30, 90, 220), "Blau", "Blue"),
    ((0, 0, 128), "Dunkelblau", "Navy"),
    ((128, 0, 160), "Lila", "Purple"),
    ((255, 105, 180), "Pink", "Pink"),
)


def hex_color(raw: str | None) -> str | None:
    """Bambu reports RRGGBBAA; Home Assistant wants #RRGGBB."""
    if not raw or len(raw) < 6:
        return None
    try:
        int(raw[:6], 16)
    except ValueError:
        return None
    return f"#{raw[:6].upper()}"


def color_name(
    color: str | None, material: str | None, catalog: dict[str, Any], language: str
) -> str | None:
    """Bambuddy's name for the colour ("Jade White"), else a basic colour name.

    The same hex is a different colour in different product lines (#FFFFFF is
    Jade White in PLA Basic, Ivory White in PLA Matte), so the material-specific
    entry wins, exactly as Bambuddy's own UI resolves it.
    """
    if not color:
        return None
    key = color.lstrip("#").lower()
    if material:
        name = (catalog.get("by_material") or {}).get(f"{material.strip().lower()}|{key}")
        if name:
            return name
    name = (catalog.get("colors") or {}).get(key)
    if name:
        return name

    rgb = tuple(int(key[i : i + 2], 16) for i in (0, 2, 4))
    nearest = min(
        _BASIC_COLORS, key=lambda c: sum((a - b) ** 2 for a, b in zip(c[0], rgb, strict=True))
    )
    return nearest[1] if language.startswith("de") else nearest[2]


def spool_picture(color: str) -> str:
    """A spool-shaped circle in the filament colour as a data URI.

    Base64 because Home Assistant puts entity pictures into CSS url(...)
    without quotes, where the spaces and quotes of a plain SVG break it.
    """
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
        f'<circle cx="12" cy="12" r="11" fill="{color}" stroke="#888" stroke-width="1"/>'
        '<circle cx="12" cy="12" r="3.5" fill="#fff" stroke="#888" stroke-width="1"/></svg>'
    )
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()
