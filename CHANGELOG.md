# Changelog

The section of a version becomes its GitHub release notes, which Home Assistant
shows under **Settings → Updates** when the update is offered.

## 0.14.0

- **New card "Bambuddy Drucker"** (`custom:bambuddy-printer-card`): one printer with a big
  progress ring in the colour of the filament in use, the print name and the loaded filament.
  Made for kitchen and hallway dashboards; add it once per printer.
- "Current print" keeps the name of a finished or failed print until the printer is idle again.

## 0.13.0

- **Spool warning:** new binary sensor "Filament low" per printer. It turns on when an AMS
  spool has 10 % or less left. Change the level (or 0 = off) under
  *Settings → Devices & services → Bambuddy → Configure*.
- Card: hint "Spool running low" on the printer and the slot's percentage in orange.
- Use it in automations, e.g. to get a message on your phone.

## 0.12.0

- **Diagnostics:** *Settings → Devices & services → Bambuddy → ⋮ → Download diagnostics*
  creates a file for bug reports. API key, URL, serial numbers and notify targets are removed.
- **Clean uninstall:** removing the last Bambuddy entry also removes the dashboard card resource.
- **Fixed:** deprecation warning "uses `via_device`" in the log on Home Assistant 2026.8 and newer.
- Camera access tokens no longer appear in error messages in the log.
- Release notes (this file) are now shown in the update dialog.

## 0.11.1

- Fixed: the card was missing from the card picker and stayed a spinner in edit mode.

## 0.11.0

- Card: gear button on each printer opens the detail window (also on phones).
- Card: uses the full width of a section; detail window with plan and "notify when done".

## 0.10.0

- Schedule (estimated start/end per job), filament check, print events, blueprints,
  queue actions, print statistics and the wall layout of the card.

## 0.9.0

- Card: printers as separate tiles, collapsible job lists.

## 0.8.0

- Per-printer queue in the card, more reliable card loading, English README.

## 0.7.0

- Own icon, MIT license, automatic releases.

## 0.6.0

- First release via HACS: printers, AMS/filament, cover image, camera, controls,
  queue as a to-do list and the dashboard card.
