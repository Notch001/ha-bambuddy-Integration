# Bambuddy for Home Assistant

<img src="custom_components/bambuddy/brand/icon.png" alt="" width="72" align="right">

[![Validate](https://github.com/Notch001/ha-bambuddy-integration/actions/workflows/validate.yml/badge.svg)](https://github.com/Notch001/ha-bambuddy-integration/actions/workflows/validate.yml)
[![Release](https://img.shields.io/github/v/release/Notch001/ha-bambuddy-integration)](https://github.com/Notch001/ha-bambuddy-integration/releases)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)

🇩🇪 [Deutsche Anleitung](README.de.md)

Unofficial Home Assistant integration for [Bambuddy](https://github.com/maziggy/bambuddy), the self-hosted manager for Bambu Lab printers, **and for PrintDog** (printer service of the Dammer Manufaktur workshop, 0.9.1 or newer; detected automatically). Where other integrations show single printers, this one knows your **whole print farm and its queue**.

- **Printer status:** state, current print with preview, progress, remaining time, end time, temperatures, errors, "clear the build plate".
- **Print queue:** waiting and running jobs per printer and overall, as a to-do list you can **reorder and clean up** right in Home Assistant.
- **Schedule:** estimated start and end of every queued job, "free from" per printer and "print farm done at".
- **Filament check** *(optional)*: warns when a queued job needs a filament that isn't loaded on its printer.
- **AMS and filament:** per slot the filament with colour name (e.g. "PLA Basic · Jade White") and remaining amount, AMS humidity and temperature, and a **warning when a spool runs low** (threshold adjustable).
- **Camera, controls:** live camera; pause, resume, stop, chamber light, print speed, "build plate cleared".
- **Actions:** move a job to the front, skip it, print something again or print a library file – from automations, scripts or voice assistants.
- **Statistics:** prints, success rate, print time and filament from Bambuddy; **costs** *(optional)* for filament and energy.
- **Blueprints** *(optional)*: phone notifications with a **Cleared** button, and automatic power for your printers' smart plugs.
- **Dashboard card** with a **wall tablet mode**, included and loaded automatically.

<img src="docs/card.png" alt="Bambuddy card (sample data)" width="640">

## Where do I find what?

| What | Where |
|---|---|
| **Everything at a glance, the detail window, notify when done** | the **Bambuddy card** on your dashboard; tap the ⚙ gear (or the printer's name) to open its detail window |
| Card options (layout, schedule, filament check, sections) | dashboard → edit → the card → its editor |
| Polling interval, **cost sensors**, **spool warning level**, **notification targets** | **Settings** → **Devices & services** → **Bambuddy** → **Configure** |
| Queue, "print farm done at", statistics, costs | **Settings** → **Devices & services** → **Bambuddy** → device **Bambuddy** |
| Per printer: "Free from", "In use", "Print event", "Notify when done", AMS slots … | same place → the printer's device |
| The queue as a list (reorder, delete) | sidebar → **To-do lists** → "Print queue" |
| Notifications with "Cleared" button, automatic power | import the [blueprints](#notifications-and-automatic-power-blueprints), then **Settings** → **Automations & scenes** → **Blueprints** |
| Actions (print again, skip, …) | **Developer tools** → **Actions**, search "Bambuddy" |

## Using PrintDog instead of Bambuddy

- **New install:** add the integration as usual and enter the PrintDog address (for example `http://192.168.200.86:8090`) and the PrintDog API key (PrintDog → *Settings* → *Directly from Orca Slicer*). The integration detects PrintDog and names the entry **PrintDog**.
- **Existing Bambuddy entry:** *Settings → Devices & services → Bambuddy → ⋮ → Reconfigure*, enter the PrintDog address and key. The entry is switched, so devices, entity ids, dashboards and automations survive.
- **Differences:** the camera shows snapshots (no live stream); *start job* is not available, PrintDog starts a waiting job when the plate is cleared; costs are not calculated by PrintDog (the energy sensors show kWh from the measuring plugs you configure per printer in PrintDog).
- If you use the *automatic power* blueprint **and** PrintDog's "switch after print end" for the same plug, both switch it - use only one.

## Requirements

- Home Assistant 2025.3 or newer (2026.3+ shows the integration icon)
- A running Bambuddy server that Home Assistant can reach
- [HACS](https://hacs.xyz/) (recommended)

## Installation

### 1. Create an API key in Bambuddy

Only needed if authentication is enabled in Bambuddy. Open Bambuddy → **Settings** → **API Keys** → **Create Key**, name it e.g. `Home Assistant`, and tick:

| Permission | Needed for |
|---|---|
| **Read Status** | everything you see (required) |
| **Control Printer** | pause, resume, stop, light, speed, "build plate cleared" |
| **Manage Queue** | reordering/removing jobs, the queue actions |

Copy the key right away (it starts with `bb_`); it is only shown once.

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
2. Enter the **Bambuddy URL** (the address you open Bambuddy with, e.g. `http://192.168.1.50:8000`) and the **API key** (empty if Bambuddy has no login).

You get one device "Bambuddy" (queue, schedule, statistics) and one device per printer. Printers, AMS units and spools added later appear automatically. Under **Configure** you can change the polling interval (default 30 s), switch on the **cost sensors**, set the **spool warning level** (default 10 %, 0 = off) and choose **notification targets** (e.g. `mobile_app_your_phone`) for "Notify when done".

## Dashboard card

The integration ships its own card and registers it as a dashboard resource automatically. Edit a dashboard → **Add card** → search for **Bambuddy**. The card finds all printers by itself; in the editor you pick printers, the layout and which sections to show.

```yaml
type: custom:bambuddy-card
title: 3D printers           # optional
layout: card                 # card | wall (wall tablet)
printers: []                 # optional: device IDs, empty = all printers
show_temperatures: true
show_ams: true
show_controls: true          # needs "Control Printer"
show_camera: false
show_timeline: true          # schedule with estimated times
show_filament_check: false   # warn about filament that isn't loaded
show_printer_queue: true     # jobs waiting for a printer, right under it
show_queue: true             # all other jobs
collapse_queue: false        # start with the job lists collapsed
queue_limit: 5               # max. jobs per list
```

- The card always uses the full width of its section. For the full page width: edit the section (pencil) and set its width to the full page.
<img src="docs/dialog.png" alt="Detail window (sample data)" width="520">

- **Detail window:** tap the ⚙ gear next to a printer's state (or its name, or a tile in wall mode) for its current print with end time, **Notify when done**, "free from", and every planned job with estimated start and end.
- Each printer is a tile with a coloured top edge for its state; tiles sit side by side on wide screens.
- Job lists and the schedule collapse when you tap their header; the browser remembers it.
- Waiting jobs show their filament colours and the estimated start ("approx. 14:30").
- **Schedule:** one bar per printer – the running print in the state colour, queued jobs after it. Jobs for "any <model>" are hatched where Bambuddy is expected to send them.
- **Wall tablet mode** (`layout: wall`): large progress rings, a clock and a summary (printing / ready / waiting / all done at), the next job per printer, and a big **Cleared** button. Made for a tablet on the wall.
<img src="docs/wall.png" alt="Wall tablet mode (sample data)" width="640">

- **One card per printer:** add the card several times, pick one printer in each and switch off `show_queue` in all but one.

## Printer card (one printer)

A second, simple card for kitchen or hallway dashboards: one printer, a big progress ring, the print name and the filament in use. Add it once per printer: **Add card** → **Bambuddy Drucker** → pick the printer.

<img src="docs/printer-card.png" alt="Printer card (sample data)" width="640">

```yaml
type: custom:bambuddy-printer-card
printer: <device id>     # chosen in the editor
layout: auto             # auto | vertical (ring on top, values below)
ring_color: filament     # filament | state
show_time: false         # remaining time and end time
show_cover: false        # print preview faintly inside the ring
```

- While printing, the ring has the colour of the filament in use (white and black get an outline so they stay visible).
- Finished: full ring with a tick and the name of the finished print. Idle: the loaded spools as colour dots.
- **Vertical** (`layout: vertical`): the ring on top, all values centred below; ring and text grow with the card, and every card in a row keeps the same ring size. Good for wall tablets with wide, fixed-height cards.
- **Width:** by default a third of a section, so three printers fit side by side. Change it per card in the editor's **Layout** tab. The card adapts to any width: stacked when narrow, even more compact when very narrow (chip and icons hidden).

## Schedule and filament check

How the estimate works: a printer is busy until its print's remaining time is over, then its waiting jobs follow one after another (using their print time and any scheduled start). Jobs for "any <model>" go to whichever printer of that model is free first. These are estimates – changing filament, clearing the plate or a failed print shift them.

The filament check compares the filament types a job needs with what's loaded in the AMS and on the external holder of the printer it will run on, and passes on Bambuddy's own "not enough filament on the spool" verdict. In the card it is off by default (`show_filament_check: true` turns it on); the data is always available as job attributes.

## Notifications and automatic power (blueprints)

Both are optional. Import them with one click, then create an automation from them:

| Blueprint | What it does | Import |
|---|---|---|
| **Print notifications** | Phone notification on print finished / failed / started, "clear the build plate" (with a **Cleared** button that releases the next job) and errors; German or English | [![Import](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FNotch001%2Fha-bambuddy-integration%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fbambuddy%2Fprint_notifications.yaml) |
| **Automatic power** | Switches a printer's smart plug off once it is unused (nothing printing, nothing waiting for it, cooled down) and back on when a job is waiting for it | [![Import](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FNotch001%2Fha-bambuddy-integration%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fbambuddy%2Fauto_power.yaml) |

The notifications need the Home Assistant companion app on your phone; the **Cleared** button needs "Control Printer". For automatic power, create one automation per printer. If you already let Bambuddy switch plugs ("auto off after print"), use only one of the two.

## Actions

Usable in automations, scripts and with voice assistants (**Developer tools** → **Actions**):

| Action | What it does |
|---|---|
| `bambuddy.move_job_to_front` | moves a waiting job to the front (`job_id`) |
| `bambuddy.cancel_job` | skips a waiting job (`job_id`) |
| `bambuddy.start_job` | starts a job that waits for a manual start (`job_id`) |
| `bambuddy.print_again` | queues an earlier print again, found by `name` (newest match) or `archive_id`; optional printer |
| `bambuddy.print_file` | queues a library file by `name` or `file_id` on a printer |
| `bambuddy.clear_plate` | tells Bambuddy the build plate is clear |

Job IDs are in the `jobs` attributes and are the item IDs of the to-do list. `print_again` and `print_file` return the new job ID. Example:

```yaml
action: bambuddy.print_again
data:
  name: Kabelclip
```

The queue actions need "Manage Queue". In the to-do list "Print queue" you can drag waiting jobs into a new order and delete them (= skip in Bambuddy).

## Entities

### Per printer

| Entity | Description |
|---|---|
| Status | Idle, Preparing, Printing, Paused, Finished, Failed, Offline |
| Current print, Print stage | file name (kept after the print finished or failed until the printer is idle again); e.g. "Heatbed preheating" |
| Progress, Remaining time, Estimated end | %, minutes, timestamp |
| Free from | when everything planned for the printer is done; attribute `schedule` |
| Current layer, Total layers | |
| Nozzle / bed / chamber temperature | current and target |
| Queue | jobs pinned to this printer; attributes `next_job`, `jobs` |
| Errors | number of HMS messages; details in `errors` |
| Online, Printing, Error, Clear build plate | binary sensors |
| In use | on while printing, a job is waiting for it, or it is still hot – off means it can be switched off |
| Notify when done | switch: on = the next finished or failed print sends a notification to the targets from **Configure** (or appears in Home Assistant's notifications), then it switches itself off |
| Print event | fires `print_started`, `print_finished`, `print_failed`, `plate_clear_required`, `error` (attributes `job`, `next_job`) |
| Nozzle | diameter; type in `nozzles` |
| Print preview, Camera | image of the current print; snapshot and live stream |
| Pause / Resume / Stop print, Build plate cleared | buttons, only available when they make sense |
| Chamber light, Print speed | light; Silent, Standard, Sport, Ludicrous |
| Door, Wi-Fi signal, fans, SD card, timelapse | disabled by default |

### AMS and filament

| Entity | Description |
|---|---|
| AMS 1 slot 1 … / External spool | filament and colour, e.g. "PLA Basic · Jade White". Attributes: `type`, `color`, `color_name`, `remaining` (%, RFID spools), `nozzle_temp_min`, `nozzle_temp_max`, `active`, `ams`, `slot` |
| AMS 1 humidity / temperature / drying remaining | drying only if the AMS can dry |
| Filament low | binary sensor (per printer): on when an AMS spool has the warning level or less left (**Configure**, default 10 %). Attribute `spools` lists them. Spools whose level the AMS can't measure (shown without %) are ignored. The card shows a hint and marks the slot. |

### Bambuddy (queue, schedule, statistics)

| Entity | Description |
|---|---|
| Queued print jobs, Running print jobs | count; attributes `next_job`, `jobs` |
| Print queue | to-do list, reorderable |
| Print farm done at | when all running and estimable queued jobs are done |
| Prints total / this month / today | attributes on the total: `successful`, `failed`, `cancelled`, `by_printer`, `by_filament_type` |
| Success rate | successful ÷ (successful + failed) |
| Print time total, Filament total / this month | hours, grams |
| *Filament cost total / this month* | only with the cost option, in Bambuddy's currency |
| *Energy total / this month, Energy cost total / this month* | only with the cost option; needs smart plugs set up in Bambuddy |

Each `jobs` entry has `id`, `name`, `status`, `printer`, `printer_id`, `position`, `scheduled_time`, `started_at`, `print_time_minutes`, `filament_type`, `filament_colors`, `filament_grams`, `estimated_cost`, `manual_start`, `waiting_reason`, `estimated_start`, `estimated_end`, `planned_printer_id`, `filament_ok`, `filament_missing`, `filament_short`.

## Updates

Every new version is published as a GitHub release. HACS shows it under **Settings** → **Updates** (check right away: HACS → **Bambuddy** → **⋮** → **Update information**). The update dialog shows what changed (from [`CHANGELOG.md`](CHANGELOG.md)). Restart Home Assistant after updating.

## Troubleshooting

**The card is missing from the card picker, shows a spinner there, or says "Custom element doesn't exist" in edit mode.** Update to 0.11.1 or newer and reload the page. (Older versions loaded the card too early, before Home Assistant had set up its frontend.)

**The card shows "Configuration error" / "Custom element doesn't exist" (often only on the phone).** Reload the page. In the companion app: **Settings** → **Companion app** → **Debugging** → **Reset frontend cache**. The card is registered under **Settings** → **Dashboards** → **⋮** → **Resources**.

**A button or action shows a permission error.** The API key lacks "Control Printer" or "Manage Queue". Edit the key in Bambuddy.

**Statistics stay unavailable.** Your Bambuddy version may not offer statistics yet; everything else works regardless.

**No icon in the HACS store.** HACS still loads icons only from the central brands server, which no longer accepts custom integrations. Home Assistant itself (2026.3 and newer) shows the icon under **Devices & services**, because it ships with the integration.

**Reporting a bug:** please attach the diagnostics file: **Settings** → **Devices & services** → **Bambuddy** → **⋮** → **Download diagnostics**. API key, URL, serial numbers and notify targets are removed from it.

**Debug logs:** **Settings** → **Devices & services** → **Bambuddy** → **Enable debug logging**.

## Development

```bash
pip install -r requirements_test.txt
python -m pytest
```

A release is created automatically when the version in `custom_components/bambuddy/manifest.json` changes on `main`.

## License

MIT, see [LICENSE](LICENSE). This is a community project, not affiliated with the Bambuddy project or Bambu Lab.
