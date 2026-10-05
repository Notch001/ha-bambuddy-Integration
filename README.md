# Bambuddy for Home Assistant

<img src="custom_components/bambuddy/brand/icon.png" alt="" width="72" align="right">

[![Validate](https://github.com/Notch001/ha-bambuddy-integration/actions/workflows/validate.yml/badge.svg)](https://github.com/Notch001/ha-bambuddy-integration/actions/workflows/validate.yml)
[![Release](https://img.shields.io/github/v/release/Notch001/ha-bambuddy-integration)](https://github.com/Notch001/ha-bambuddy-integration/releases)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)

🇩🇪 [Deutsche Anleitung](README.de.md)

Unofficial Home Assistant integration for [Bambuddy](https://github.com/maziggy/bambuddy), the self-hosted manager for Bambu Lab printers.

- **Printer status:** state, current print with preview, progress, remaining time, estimated end, layer, temperatures, online/offline, errors, "clear the build plate".
- **Print queue:** waiting and running jobs, overall and per printer, as a to-do list and as sensors.
- **AMS and filament:** per slot the filament and its colour (e.g. "PLA Basic · Jade White") and remaining amount, plus humidity and temperature of every AMS.
- **Camera:** snapshot and live stream, relayed through Bambuddy.
- **Controls:** pause, resume, stop, confirm a cleared build plate, chamber light, print speed.
- **Dashboard card:** one card for all printers and the queue, included and loaded automatically.

<img src="docs/card.png" alt="Bambuddy card (sample data)" width="420">

## Requirements

- Home Assistant 2025.3 or newer (2026.3+ shows the integration icon)
- A running Bambuddy server that Home Assistant can reach
- [HACS](https://hacs.xyz/) (recommended)

## Installation

### 1. Create an API key in Bambuddy

Only needed if authentication is enabled in Bambuddy.

1. Open Bambuddy → **Settings** → **API Keys** → **Create Key**, name it e.g. `Home Assistant`.
2. Tick **Read Status**. To control printers from Home Assistant (pause, stop, light, speed) also tick **Control Printer**. Everything else can stay off.
3. **Copy the key right away** (it starts with `bb_`). It is only shown once.

### 2. Install via HACS

1. Open **HACS** → **⋮** (top right) → **Custom repositories**.
2. Repository `https://github.com/Notch001/ha-bambuddy-integration`, type **Integration** → **Add**.
3. Search for **Bambuddy** in HACS, open it and click **Download**.
4. Restart Home Assistant.

<details>
<summary>Without HACS</summary>

Copy `custom_components/bambuddy` from this repository to `/config/custom_components/bambuddy` and restart Home Assistant.
</details>

### 3. Set up the integration

1. **Settings** → **Devices & services** → **Add integration** → **Bambuddy**.
2. Enter the **Bambuddy URL**, the same address you open Bambuddy with in the browser, e.g. `http://192.168.1.50:8000`.
3. Paste the **API key**, or leave it empty if Bambuddy has authentication disabled.

You get one device "Bambuddy" for the queue and one device per printer. Printers, AMS units and spools added later appear automatically. The polling interval (default 30 s) can be changed under **Configure**.

## Dashboard card

The integration ships its own card and registers it as a dashboard resource automatically. Nothing else to install.

**Add it:** edit a dashboard → **Add card** → search for **Bambuddy**. The card finds all printers by itself. In the card editor you can pick printers and switch sections on or off.

```yaml
type: custom:bambuddy-card
title: 3D printers           # optional
printers: []                 # optional: device IDs, empty = all printers
show_temperatures: true
show_ams: true
show_controls: true          # needs the "Control Printer" permission
show_camera: false
show_printer_queue: true     # jobs waiting for a printer, shown right under it
show_queue: true             # all other jobs (any printer / printers not on this card)
queue_limit: 5               # max. jobs per list
```

Tapping a value opens its details. "Stop" asks for confirmation.

## Entities

### Per printer

| Entity | Description |
|---|---|
| Status | Idle, Preparing, Printing, Paused, Finished, Failed, Offline |
| Current print, Print stage | file name; e.g. "Heatbed preheating" |
| Progress, Remaining time, Estimated end | %, minutes, timestamp |
| Current layer, Total layers | |
| Nozzle / bed / chamber temperature | current and target (chamber and second nozzle only if the printer reports them) |
| Queue | jobs pinned to this printer; attributes `next_job`, `jobs` |
| Errors | number of HMS messages; details in `errors` |
| Online, Printing, Error, Clear build plate | binary sensors |
| Nozzle | diameter; type in `nozzles` |
| Print preview | image of the current print |
| Camera | snapshot and live stream |
| Door, Wi-Fi signal, fans, SD card, timelapse | disabled by default |

### AMS and filament

| Entity | Description |
|---|---|
| AMS 1 slot 1 … | filament and colour, e.g. "PLA Basic · Jade White", otherwise "Empty"/"Unknown". Colour names come from Bambuddy's colour catalogue, with a basic colour name as fallback. The entity picture is a spool in the filament colour. Attributes: `type`, `color`, `color_name`, `remaining` (%, RFID spools only), `nozzle_temp_min`, `nozzle_temp_max`, `active`, `ams`, `slot` |
| External spool | same for the external spool holder |
| AMS 1 humidity / temperature | |
| AMS 1 drying remaining | only for printers whose AMS can dry |

### Controls (need the "Control Printer" permission)

| Entity | Description |
|---|---|
| Pause / Resume / Stop print | buttons, only available when they make sense |
| Build plate cleared | tells Bambuddy the plate is free so it can start the next job |
| Chamber light | on/off |
| Print speed | Silent, Standard, Sport, Ludicrous (during a print) |

Without the permission, Home Assistant shows an error message when pressed; nothing else happens.

### Bambuddy (queue)

| Entity | Description |
|---|---|
| Queued print jobs | count; attributes `next_job`, `jobs` (max. 50) |
| Running print jobs | count; attribute `jobs` |
| Print queue | the queue as a read-only **to-do list**: running jobs (▶) first, then waiting jobs in the order Bambuddy starts them |

Each `jobs` entry has `id`, `name`, `status`, `printer`, `printer_id`, `position`, `scheduled_time`, `started_at`, `print_time_minutes`, `filament_type`, `filament_grams`, `manual_start`, `waiting_reason`.

The to-do list appears in the sidebar under **To-do lists** and can be added to a dashboard with the built-in **To-do list** card.

## Updates

Every new version is published as a GitHub release. HACS checks for releases regularly and shows them under **Settings** → **Updates**. To check right away: HACS → **Bambuddy** → **⋮** → **Update information**. Restart Home Assistant after updating.

## Troubleshooting

**The card shows "Configuration error" / "Custom element doesn't exist" (often only on the phone).** The browser or app has not loaded the card script yet. Reload the page. In the companion app: **Settings** → **Companion app** → **Debugging** → **Reset frontend cache**, then reopen the app. Since 0.7.0 the card is also registered under **Settings** → **Dashboards** → **⋮** → **Resources**, which the apps load reliably.

**Control buttons show an error.** The API key lacks the **Control Printer** permission. Edit the key in Bambuddy or create a new one.

**Debug logs:** **Settings** → **Devices & services** → **Bambuddy** → **Enable debug logging**.

## Development

```bash
pip install -r requirements_test.txt
python -m pytest
```

A release is created automatically when the version in `custom_components/bambuddy/manifest.json` changes on `main`.

## License

MIT, see [LICENSE](LICENSE). This is a community project, not affiliated with the Bambuddy project or Bambu Lab.
