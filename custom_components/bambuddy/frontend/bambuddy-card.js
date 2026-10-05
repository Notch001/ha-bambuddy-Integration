/*
 * Bambuddy dashboard card for Home Assistant.
 *
 * Shipped and registered by the Bambuddy integration; no separate install.
 * Finds the integration's entities by their translation keys, so it works
 * without any configuration:  type: custom:bambuddy-card
 */

const CARD_VERSION = "0.10.0";

const TEXT = {
  de: {
    queue: "Warteschlange",
    queue_empty: "Keine Aufträge in der Warteschlange",
    more: "weitere",
    layer: "Schicht",
    plate: "Druckplatte räumen, bevor der nächste Auftrag startet",
    plate_done: "Geräumt",
    errors: "Fehlermeldungen",
    error_one: "Fehlermeldung",
    nozzle: "Düse",
    bed: "Bett",
    chamber: "Bauraum",
    external: "Extern",
    empty: "Leer",
    pause: "Pause",
    resume: "Fortsetzen",
    stop: "Abbrechen",
    light: "Licht",
    confirm_stop: "Druck wirklich abbrechen?",
    no_printers: "Keine Bambuddy-Drucker gefunden. Ist die Integration eingerichtet?",
    any: "beliebiger Drucker",
    title: "Titel",
    printers: "Drucker (leer = alle)",
    show_temperatures: "Temperaturen",
    show_ams: "AMS / Filament",
    show_controls: "Steuerung",
    show_camera: "Kamera",
    show_queue: "Warteschlange (übrige Aufträge)",
    show_printer_queue: "Warteschlange je Drucker",
    queue_limit: "Max. Aufträge je Liste",
    up_next: "Als Nächstes",
    timeline: "Zeitplan",
    details: "Details",
    done_at: "Fertig um",
    in_time: "in",
    notify_done: "Benachrichtigen, wenn fertig",
    notify_to: "an",
    notify_ha: "als Hinweis in Home Assistant",
    notify_hint: "Ziele festlegen: Einstellungen → Geräte & Dienste → Bambuddy → Konfigurieren",
    free_from: "Frei ab",
    free_now: "Jetzt frei",
    plan: "Geplant",
    predicted: "voraussichtlich auf diesem Drucker",
    nothing_planned: "Nichts geplant",
    all_entities: "Alle Werte",
    close: "Schließen",
    all_done: "Alles fertig",
    all_free: "Alle Drucker frei",
    now: "Jetzt",
    free: "frei",
    approx: "ca.",
    filament_missing: "nicht geladen",
    filament_short: "zu wenig Filament",
    printing_n: "drucken",
    waiting_n: "wartend",
    idle_n: "bereit",
    layout: "Darstellung",
    layout_card: "Karte",
    layout_wall: "Wandtablet",
    show_timeline: "Zeitplan",
    show_filament_check: "Filament-Check",
    collapse_queue: "Listen anfangs eingeklappt",
    other_jobs: "Weitere Aufträge",
  },
  en: {
    queue: "Queue",
    queue_empty: "No jobs in the queue",
    more: "more",
    layer: "Layer",
    plate: "Clear the build plate before the next job starts",
    plate_done: "Cleared",
    errors: "errors",
    error_one: "error",
    nozzle: "Nozzle",
    bed: "Bed",
    chamber: "Chamber",
    external: "External",
    empty: "Empty",
    pause: "Pause",
    resume: "Resume",
    stop: "Stop",
    light: "Light",
    confirm_stop: "Really stop the print?",
    no_printers: "No Bambuddy printers found. Is the integration set up?",
    any: "any printer",
    title: "Title",
    printers: "Printers (empty = all)",
    show_temperatures: "Temperatures",
    show_ams: "AMS / filament",
    show_controls: "Controls",
    show_camera: "Camera",
    show_queue: "Queue (remaining jobs)",
    show_printer_queue: "Queue per printer",
    queue_limit: "Max. jobs per list",
    up_next: "Up next",
    timeline: "Schedule",
    details: "Details",
    done_at: "Done at",
    in_time: "in",
    notify_done: "Notify when done",
    notify_to: "to",
    notify_ha: "as a notification in Home Assistant",
    notify_hint: "Choose targets: Settings → Devices & services → Bambuddy → Configure",
    free_from: "Free from",
    free_now: "Free now",
    plan: "Planned",
    predicted: "expected on this printer",
    nothing_planned: "Nothing planned",
    all_entities: "All values",
    close: "Close",
    all_done: "All done",
    all_free: "All printers free",
    now: "Now",
    free: "free",
    approx: "approx.",
    filament_missing: "not loaded",
    filament_short: "not enough filament",
    printing_n: "printing",
    waiting_n: "waiting",
    idle_n: "ready",
    layout: "Layout",
    layout_card: "Card",
    layout_wall: "Wall tablet",
    show_timeline: "Schedule",
    show_filament_check: "Filament check",
    collapse_queue: "Lists collapsed by default",
    other_jobs: "Other jobs",
  },
};

const STATE_COLORS = {
  running: "var(--success-color, #43a047)",
  prepare: "var(--info-color, #039be5)",
  slicing: "var(--info-color, #039be5)",
  pause: "var(--warning-color, #ffa000)",
  finish: "var(--info-color, #039be5)",
  failed: "var(--error-color, #db4437)",
  offline: "var(--disabled-text-color, #9e9e9e)",
};

const PRINTING_STATES = new Set(["running", "prepare", "slicing", "pause"]);
// Entities that exist several times per printer.
const MULTI_KEYS = new Set(["sensor.ams_tray", "sensor.external_spool", "sensor.external_spool_n", "sensor.ams_humidity"]);

const DEFAULTS = {
  show_temperatures: true,
  show_ams: true,
  show_controls: true,
  show_camera: false,
  show_queue: true,
  show_printer_queue: true,
  collapse_queue: false,
  show_timeline: true,
  show_filament_check: false,
  layout: "card",
  queue_limit: 5,
};

const COLLAPSE_STORE = "bambuddy-card:collapsed";

function loadCollapsed() {
  try {
    return JSON.parse(localStorage.getItem(COLLAPSE_STORE) || "{}");
  } catch (err) {
    return {};
  }
}

function saveCollapsed(state) {
  try {
    localStorage.setItem(COLLAPSE_STORE, JSON.stringify(state));
  } catch (err) {
    // Private mode or storage disabled: the toggle still works until reload.
  }
}

function lang() {
  const l = (document.documentElement.lang || navigator.language || "en").slice(0, 2);
  return TEXT[l] ? l : "en";
}

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c],
  );
}

function num(state) {
  const n = parseFloat(state?.state);
  return Number.isFinite(n) ? n : null;
}

function formatMinutes(min) {
  if (min == null) return "";
  const h = Math.floor(min / 60);
  const m = Math.round(min % 60);
  return h ? `${h} h ${String(m).padStart(2, "0")} min` : `${m} min`;
}

// Spool colours of a job ("#RRGGBB" or "RRGGBBAA").
function colorDots(colors) {
  return (colors || [])
    .slice(0, 6)
    .map((c) => {
      const hex = c.startsWith("#") ? c.slice(0, 7) : `#${c.slice(0, 6)}`;
      return /^#[0-9a-fA-F]{6}$/.test(hex) ? `<span class="cdot" style="background:${hex}"></span>` : "";
    })
    .join("");
}

class BambuddyCard extends HTMLElement {
  static getStubConfig() {
    return {};
  }

  static getConfigForm() {
    const t = TEXT[lang()];
    return {
      schema: [
        { name: "title", selector: { text: {} } },
        {
          name: "layout",
          default: "card",
          selector: {
            select: {
              mode: "box",
              options: [
                { value: "card", label: t.layout_card },
                { value: "wall", label: t.layout_wall },
              ],
            },
          },
        },
        {
          name: "printers",
          selector: { device: { multiple: true, filter: { integration: "bambuddy", manufacturer: "Bambu Lab" } } },
        },
        {
          type: "grid",
          name: "",
          schema: ["show_temperatures", "show_ams", "show_controls", "show_camera", "show_timeline", "show_filament_check", "show_printer_queue", "show_queue", "collapse_queue"].map((name) => ({
            name,
            default: DEFAULTS[name],
            selector: { boolean: {} },
          })),
        },
        { name: "queue_limit", default: DEFAULTS.queue_limit, selector: { number: { min: 0, max: 50, mode: "box" } } },
      ],
      computeLabel: (schema) => t[schema.name] ?? schema.name,
    };
  }

  setConfig(config) {
    this._config = { ...DEFAULTS, ...(config || {}) };
    this._collapsed = loadCollapsed();
    this._signature = null;
    if (this._hass) this._update();
  }

  set hass(hass) {
    this._hass = hass;
    this._update();
  }

  getCardSize() {
    return 3 + 4 * (this._printers?.length || 1) + (this._config?.show_queue ? 3 : 0);
  }

  getGridOptions() {
    // "full" = the whole section, however many page columns it spans.
    return { columns: "full", min_columns: 6 };
  }

  connectedCallback() {
    if (!this.shadowRoot) {
      this.attachShadow({ mode: "open" });
      this.shadowRoot.addEventListener("click", (ev) => this._onClick(ev));

    }
    if (this._hass) this._update();
    // The wall layout shows a clock and the timeline moves with time.
    if (!this._clock) this._clock = setInterval(() => this._hass && this._render(), 60000);
  }

  // ---- data -------------------------------------------------------------

  _discover() {
    const devices = {};
    for (const entry of Object.values(this._hass.entities || {})) {
      if (entry.platform !== "bambuddy" || entry.hidden || !entry.translation_key) continue;
      const key = `${entry.entity_id.split(".")[0]}.${entry.translation_key}`;
      const dev = (devices[entry.device_id] ||= { id: entry.device_id, one: {}, many: {} });
      if (MULTI_KEYS.has(key)) (dev.many[key] ||= []).push(entry.entity_id);
      else dev.one[key] = entry.entity_id;
    }
    const wanted = this._config.printers?.length ? new Set(this._config.printers) : null;
    const name = (d) => this._hass.devices?.[d.id]?.name_by_user || this._hass.devices?.[d.id]?.name || "";
    this._printers = Object.values(devices)
      .filter((d) => d.one["sensor.printer_state"] && (!wanted || wanted.has(d.id)))
      .map((d) => ({ ...d, name: name(d) }))
      .sort((a, b) => a.name.localeCompare(b.name));
    this._hub = Object.values(devices).find((d) => d.one["sensor.queue_pending"]);
  }

  _entityIds() {
    const ids = [];
    for (const d of [...this._printers, this._hub].filter(Boolean)) {
      ids.push(...Object.values(d.one));
      for (const list of Object.values(d.many)) ids.push(...list);
    }
    return ids;
  }

  _update() {
    if (!this._config || !this._hass || !this.shadowRoot) return;
    this._discover();
    const ids = this._entityIds();
    const signature =
      ids.map((id) => `${id}:${this._hass.states[id]?.last_updated}`).join("|") + `|${this._hass.language}`;
    if (signature === this._signature) return;
    this._signature = signature;
    this._render();
  }

  _state(dev, key) {
    const id = dev?.one[key];
    return id ? this._hass.states[id] : undefined;
  }

  _time(value, alwaysDay = false) {
    const date = value instanceof Date ? value : new Date(value);
    if (!value || isNaN(date)) return "";
    const sameDay = date.toDateString() === new Date().toDateString();
    return date.toLocaleString(this._hass.locale?.language || undefined, {
      ...(sameDay && !alwaysDay ? {} : { weekday: "short" }),
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  disconnectedCallback() {
    clearInterval(this._clock);
    this._clock = null;
    this._dialog = null;
    this._dialogHost?.remove();
    this._dialogHost = null;
    if (this._onKey) document.removeEventListener("keydown", this._onKey);
  }

  _fmt(stateObj) {
    if (!stateObj) return "";
    return this._hass.formatEntityState ? this._hass.formatEntityState(stateObj) : stateObj.state;
  }

  // ---- rendering --------------------------------------------------------

  _render() {
    const t = TEXT[lang()];
    if (!this._printers) return;
    if (this._config.layout === "wall") {
      this.shadowRoot.innerHTML = `<style>${STYLE}${WALL_STYLE}</style><ha-card class="wall">${this._renderWall(t)}</ha-card>`;
      this._renderDialogHost(t);
      return;
    }
    const timeline = this._config.show_timeline ? this._renderTimeline(t) : "";
    const body = this._printers.length
      ? `<div class="printers${this._printers.length === 1 ? " single" : ""}">${this._printers.map((p) => this._renderPrinter(p, t)).join("")}</div>`
      : `<div class="empty pad">${esc(t.no_printers)}</div>`;
    const queue = this._config.show_queue && this._hub ? this._renderQueue(t) : "";
    const title = this._config.title ? `<h1 class="card-title">${esc(this._config.title)}</h1>` : "";
    this.shadowRoot.innerHTML = `<style>${STYLE}</style><ha-card>${title}${body}${timeline}${queue}</ha-card>`;
    this._renderDialogHost(t);
  }

  _renderPrinter(p, t) {
    const stateObj = this._state(p, "sensor.printer_state");
    const state = stateObj?.state || "unavailable";
    const printing = PRINTING_STATES.has(state);
    const color = STATE_COLORS[state] || "var(--secondary-text-color)";

    let html = `<section class="printer" style="--accent:${color}">
      <div class="head">
        <ha-icon icon="mdi:printer-3d"></ha-icon>
        <span class="name" data-dialog="${esc(p.id)}" title="${esc(t.details)}">${esc(p.name)}<ha-icon class="info" icon="mdi:information-outline"></ha-icon></span>
        <span class="chip" style="--chip:${color}" data-more="${esc(p.one["sensor.printer_state"])}">${esc(this._fmt(stateObj))}</span>
      </div>`;

    if (printing) html += this._renderJob(p, t);

    if (this._state(p, "binary_sensor.awaiting_plate_clear")?.state === "on") {
      const btn = p.one["button.clear_plate"];
      const canPress = btn && this._hass.states[btn]?.state !== "unavailable";
      html += `<div class="banner warn"><ha-icon icon="mdi:broom"></ha-icon><span>${esc(t.plate)}</span>
        ${canPress ? `<button data-press="${esc(btn)}">${esc(t.plate_done)}</button>` : ""}</div>`;
    }

    const errors = num(this._state(p, "sensor.hms_errors"));
    if (errors) {
      html += `<div class="banner error" data-more="${esc(p.one["sensor.hms_errors"])}">
        <ha-icon icon="mdi:alert"></ha-icon><span>${errors} ${esc(errors === 1 ? t.error_one : t.errors)}</span></div>`;
    }

    if (this._config.show_temperatures) html += this._renderTemps(p, t);
    if (this._config.show_ams) html += this._renderAms(p, t);
    if (this._config.show_controls) html += this._renderControls(p, t);
    if (this._config.show_printer_queue) html += this._renderPrinterQueue(p, t);
    if (this._config.show_camera) html += this._renderCamera(p);

    return html + "</section>";
  }

  _renderJob(p, t) {
    const cover = this._state(p, "image.cover");
    const name = this._state(p, "sensor.current_print")?.state;
    const stage = this._state(p, "sensor.stage")?.state;
    const progress = num(this._state(p, "sensor.progress")) ?? 0;
    const remaining = num(this._state(p, "sensor.remaining_time"));
    const end = this._state(p, "sensor.end_time")?.state;
    const layer = num(this._state(p, "sensor.current_layer"));
    const layers = num(this._state(p, "sensor.total_layers"));

    let endText = "";
    const endDate = end ? new Date(end) : null;
    if (endDate && !isNaN(endDate)) {
      const sameDay = endDate.toDateString() === new Date().toDateString();
      endText = endDate.toLocaleString(this._hass.locale?.language || undefined, {
        ...(sameDay ? {} : { weekday: "short" }),
        hour: "2-digit",
        minute: "2-digit",
      });
    }
    const coverUrl = cover?.attributes?.entity_picture;
    const known = (v) => v && v !== "unknown" && v !== "unavailable";

    return `<div class="job">
      ${coverUrl ? `<img class="cover" src="${esc(coverUrl)}" alt="" data-more="${esc(p.one["image.cover"])}">` : ""}
      <div class="info">
        <div class="title" data-more="${esc(p.one["sensor.current_print"] || "")}">${esc(known(name) ? name : "")}</div>
        ${known(stage) ? `<div class="stage">${esc(stage)}</div>` : ""}
        <div class="bar" data-more="${esc(p.one["sensor.progress"] || "")}"><div style="width:${Math.min(100, Math.max(0, progress))}%"></div></div>
        <div class="meta">
          <span class="pct">${Math.round(progress)} %</span>
          ${remaining != null ? `<span><ha-icon icon="mdi:timer-sand"></ha-icon>${esc(formatMinutes(remaining))}</span>` : ""}
          ${endText ? `<span><ha-icon icon="mdi:flag-checkered"></ha-icon>${esc(endText)}</span>` : ""}
          ${layer != null && layers ? `<span><ha-icon icon="mdi:layers-outline"></ha-icon>${layer} / ${layers}</span>` : ""}
        </div>
      </div>
    </div>`;
  }

  _renderTemps(p, t) {
    const pill = (icon, label, curKey, targetKey) => {
      const cur = num(this._state(p, curKey));
      if (cur == null) return "";
      const target = targetKey ? num(this._state(p, targetKey)) : null;
      const heating = target ? " heating" : "";
      return `<span class="pill${heating}" data-more="${esc(p.one[curKey])}" title="${esc(label)}">
        <ha-icon icon="${icon}"></ha-icon>${Math.round(cur)}${target ? ` / ${Math.round(target)}` : ""} °C</span>`;
    };
    const pills = [
      pill("mdi:printer-3d-nozzle-heat", t.nozzle, "sensor.nozzle_temperature", "sensor.nozzle_target_temperature"),
      pill("mdi:printer-3d-nozzle-heat", `${t.nozzle} 2`, "sensor.nozzle_2_temperature", null),
      pill("mdi:radiator", t.bed, "sensor.bed_temperature", "sensor.bed_target_temperature"),
      pill("mdi:thermometer", t.chamber, "sensor.chamber_temperature", null),
    ].join("");
    return pills ? `<div class="pills">${pills}</div>` : "";
  }

  _renderAms(p, t) {
    const trays = (p.many["sensor.ams_tray"] || [])
      .map((id) => this._hass.states[id])
      .filter(Boolean)
      .sort((a, b) =>
        String(a.attributes.ams).localeCompare(String(b.attributes.ams), undefined, { numeric: true }) ||
        (a.attributes.slot || 0) - (b.attributes.slot || 0),
      );
    const externals = [...(p.many["sensor.external_spool"] || []), ...(p.many["sensor.external_spool_n"] || [])]
      .map((id) => this._hass.states[id])
      .filter(Boolean);
    if (!trays.length && !externals.length) return "";

    const humidity = (p.many["sensor.ams_humidity"] || [])
      .map((id) => this._hass.states[id])
      .filter((s) => s && num(s) != null);

    const spool = (s, label) => {
      const a = s.attributes;
      const empty = s.state === "empty";
      const color = empty ? "transparent" : a.color || "var(--disabled-text-color)";
      const remain = a.remaining != null ? `${a.remaining} %` : "";
      return `<div class="spool${a.active ? " active" : ""}${empty ? " empty" : ""}" data-more="${esc(s.entity_id)}"
          title="${esc(this._fmt(s))}">
        <div class="dot" style="--spool:${esc(color)}"></div>
        <div class="slot">${esc(label)}</div>
        <div class="fil">${esc(empty ? t.empty : a.type || this._fmt(s))}</div>
        ${remain ? `<div class="rem">${esc(remain)}</div>` : ""}
      </div>`;
    };

    const units = new Set(trays.map((s) => s.attributes.ams));
    const multiUnit = units.size > 1;
    const spools = [
      ...trays.map((s) => spool(s, multiUnit ? `${s.attributes.ams}·${s.attributes.slot}` : String(s.attributes.slot ?? ""))),
      ...externals.map((s) => spool(s, t.external)),
    ].join("");
    const hum = humidity
      .map((s) => `<span class="hum" data-more="${esc(s.entity_id)}"><ha-icon icon="mdi:water-percent"></ha-icon>${esc(this._fmt(s))}</span>`)
      .join("");
    return `<div class="ams"><div class="spools">${spools}</div>${hum ? `<div class="hums">${hum}</div>` : ""}</div>`;
  }

  _renderControls(p, t) {
    const button = (key, icon, label, cls = "") => {
      const id = p.one[key];
      if (!id || this._hass.states[id]?.state === "unavailable" || !this._hass.states[id]) return "";
      return `<button class="${cls}" data-press="${esc(id)}"${key === "button.stop" ? ' data-confirm="1"' : ""}>
        <ha-icon icon="${icon}"></ha-icon>${esc(label)}</button>`;
    };
    const lightId = p.one["light.chamber_light"];
    const light = lightId ? this._hass.states[lightId] : null;
    const lightBtn =
      light && light.state !== "unavailable"
        ? `<button class="${light.state === "on" ? "on" : ""}" data-toggle="${esc(lightId)}">
            <ha-icon icon="${light.state === "on" ? "mdi:lightbulb" : "mdi:lightbulb-off"}"></ha-icon>${esc(t.light)}</button>`
        : "";
    const speedId = p.one["select.print_speed"];
    const speed = speedId ? this._hass.states[speedId] : null;
    const speedBtn =
      speed && speed.state !== "unavailable"
        ? `<button data-more="${esc(speedId)}"><ha-icon icon="mdi:speedometer"></ha-icon>${esc(this._fmt(speed))}</button>`
        : "";
    const buttons = [
      button("button.pause", "mdi:pause", t.pause),
      button("button.resume", "mdi:play", t.resume),
      button("button.stop", "mdi:stop", t.stop, "danger"),
      speedBtn,
      lightBtn,
    ].join("");
    return buttons ? `<div class="controls">${buttons}</div>` : "";
  }

  _renderCamera(p) {
    const cam = this._state(p, "camera.camera");
    const url = cam?.attributes?.entity_picture;
    if (!url || cam.state === "unavailable") return "";
    return `<img class="camera" src="${esc(url)}" alt="" data-more="${esc(p.one["camera.camera"])}">`;
  }

  _jobRow(job, marker, cls, t, showPrinter = true) {
    const details = [
      showPrinter ? job.printer || t.any : null,
      job.print_time_minutes ? formatMinutes(job.print_time_minutes) : null,
      job.filament_type,
      cls !== "running" && job.estimated_start ? `${t.approx} ${this._time(job.estimated_start)}` : null,
    ].filter(Boolean);
    const warn = [];
    if (this._config.show_filament_check) {
      if (job.filament_ok === false) warn.push(`${job.filament_missing.join(", ")} ${t.filament_missing}`);
      if (job.filament_short) warn.push(t.filament_short);
    }
    return `<li class="${cls}">
      <span class="marker">${marker}</span>
      <span class="job-name">${esc(job.name || "?")}${colorDots(job.filament_colors)}</span>
      ${details.length ? `<span class="job-details">${esc(details.join(" · "))}</span>` : ""}
      ${warn.length ? `<span class="job-warn"><ha-icon icon="mdi:alert"></ha-icon>${esc(warn.join(" · "))}</span>` : ""}
      ${job.waiting_reason ? `<span class="job-wait">${esc(job.waiting_reason)}</span>` : ""}
    </li>`;
  }

  _isCollapsed(key) {
    return this._collapsed?.[key] ?? Boolean(this._config.collapse_queue);
  }

  _toggleCollapsed(key) {
    this._collapsed = { ...loadCollapsed(), [key]: !this._isCollapsed(key) };
    saveCollapsed(this._collapsed);
    this._render();
  }

  _chevron(key) {
    return `<ha-icon class="chevron" icon="${this._isCollapsed(key) ? "mdi:chevron-down" : "mdi:chevron-up"}"></ha-icon>`;
  }

  _limit() {
    return Number(this._config.queue_limit ?? DEFAULTS.queue_limit);
  }

  // Jobs pinned to this printer, right under it.
  _renderPrinterQueue(p, t) {
    const queueState = this._state(p, "sensor.printer_queue");
    const jobs = queueState?.attributes?.jobs || [];
    if (!jobs.length) return "";
    const key = `printer:${p.id}`;
    const collapsed = this._isCollapsed(key);
    const limit = this._limit();
    const hidden = Math.max(0, jobs.length - limit);
    const rows = jobs.slice(0, limit).map((j, i) => this._jobRow(j, `${i + 1}.`, "", t, false)).join("");
    const peek = collapsed ? `<span class="peek">${esc(jobs[0].name || "")}</span>` : "";
    return `<div class="pqueue${collapsed ? " collapsed" : ""}">
      <div class="subhead" data-collapse="${esc(key)}" role="button" aria-expanded="${!collapsed}">
        <ha-icon icon="mdi:tray-full"></ha-icon><span class="label">${esc(t.up_next)}</span>${peek}
        <span class="count">${jobs.length}</span>${this._chevron(key)}
      </div>
      ${collapsed ? "" : `<ol>${rows}</ol>
      ${hidden ? `<div class="more" data-more="${esc(p.one["sensor.printer_queue"])}">+ ${hidden} ${esc(t.more)}</div>` : ""}`}
    </div>`;
  }

  _renderQueue(t) {
    let printing = this._state(this._hub, "sensor.queue_printing")?.attributes?.jobs || [];
    let pending = this._state(this._hub, "sensor.queue_pending")?.attributes?.jobs || [];
    const perPrinter = this._config.show_printer_queue;
    if (perPrinter) {
      // Jobs already shown under their printer (running job or "up next")
      // are left out; what remains is unassigned or for printers not on
      // this card.
      const shown = new Set(
        this._printers
          .map((p) => this._state(p, "sensor.printer_queue")?.attributes?.printer_id)
          .filter((id) => id != null),
      );
      printing = printing.filter((j) => j.printer_id == null || !shown.has(j.printer_id));
      pending = pending.filter((j) => j.printer_id == null || !shown.has(j.printer_id));
      if (!printing.length && !pending.length) return "";
    }
    const limit = this._limit();
    const rows = [
      ...printing.map((j) => this._jobRow(j, '<ha-icon icon="mdi:play"></ha-icon>', "running", t)),
      ...pending.slice(0, limit).map((j, i) => this._jobRow(j, `${i + 1}.`, "", t)),
    ].join("");
    const hidden = Math.max(0, pending.length - limit);
    const list =
      printing.length || pending.length
        ? `<ol>${rows}</ol>${hidden ? `<div class="more" data-more="${esc(this._hub.one["todo.queue"] || this._hub.one["sensor.queue_pending"])}">+ ${hidden} ${esc(t.more)}</div>` : ""}`
        : `<div class="empty">${esc(t.queue_empty)}</div>`;

    const collapsed = this._isCollapsed("queue");
    return `<section class="queue${collapsed ? " collapsed" : ""}">
      <div class="head" data-collapse="queue" role="button" aria-expanded="${!collapsed}">
        <ha-icon icon="mdi:format-list-numbered"></ha-icon>
        <span class="name">${esc(perPrinter ? t.other_jobs : t.queue)}</span>
        <span class="count">${pending.length + printing.length}</span>${this._chevron("queue")}
      </div>
      ${collapsed ? "" : list}
    </section>`;
  }

  _schedules() {
    return this._printers.map((p) => ({
      p,
      entries: this._state(p, "sensor.free_at")?.attributes?.schedule || [],
      color: STATE_COLORS[this._state(p, "sensor.printer_state")?.state] || "var(--primary-color)",
    }));
  }

  _renderTimeline(t, collapsible = true) {
    const rows = this._schedules();
    const now = Date.now();
    const ends = rows.flatMap((r) => r.entries.map((e) => Date.parse(e.end || e.start))).filter((v) => !isNaN(v));
    const farmDone = this._state(this._hub, "sensor.farm_done_at")?.state;
    const doneText =
      farmDone && !["unknown", "unavailable"].includes(farmDone) ? `${t.all_done}: ${this._time(farmDone)}` : t.all_free;
    const key = "timeline";
    const collapsed = collapsible && this._isCollapsed(key);
    const head = `<div class="head" ${collapsible ? `data-collapse="${key}" role="button"` : ""}>
        <ha-icon icon="mdi:chart-timeline"></ha-icon><span class="name">${esc(t.timeline)}</span>
        <span class="done" data-more="${esc(this._hub?.one["sensor.farm_done_at"] || "")}">${esc(doneText)}</span>
        ${collapsible ? this._chevron(key) : ""}</div>`;
    if (!ends.length || collapsed) return `<section class="timeline${collapsed ? " collapsed" : ""}">${head}</section>`;

    const hour = 3600e3;
    const span = Math.min(48 * hour, Math.max(2 * hour, Math.max(...ends) - now));
    const step = [1, 2, 3, 4, 6, 12, 24].find((h) => span / (h * hour) <= 6) * hour;
    const pct = (ms) => Math.max(0, Math.min(100, ((ms - now) / span) * 100));
    const ticks = [];
    for (let tick = Math.ceil(now / step) * step; tick < now + span; tick += step) {
      ticks.push(`<span class="tick" style="left:${pct(tick)}%">${esc(this._time(new Date(tick)))}</span>`);
    }
    const body = rows
      .map(({ p, entries, color }) => {
        const segs = entries
          .map((e, i) => {
            const start = Date.parse(e.start);
            if (isNaN(start)) return "";
            const end = e.end ? Date.parse(e.end) : now + span;
            const left = pct(start);
            const width = Math.max(0.8, pct(end) - left);
            const cls = ["seg", e.running ? "running" : i % 2 ? "alt" : "", e.end ? "" : "open", e.predicted ? "predicted" : ""].join(" ");
            const title = `${e.name || "?"} · ${this._time(e.start)}${e.end ? `–${this._time(e.end)}` : ""}`;
            return `<span class="${cls}" style="left:${left}%;width:${width}%;${e.running ? `--seg:${color}` : ""}" title="${esc(title)}">${esc(e.name || "")}</span>`;
          })
          .join("");
        return `<div class="tl-row"><span class="tl-name" title="${esc(p.name)}">${esc(p.name)}</span>
          <div class="tl-track">${segs || `<span class="tl-free">${esc(t.free)}</span>`}</div></div>`;
      })
      .join("");
    return `<section class="timeline">${head}
      <div class="tl">${body}<div class="tl-row axis"><span class="tl-name"></span><div class="tl-track">${ticks.join("")}</div></div></div>
    </section>`;
  }

  _ring(progress, color, inner) {
    const r = 54;
    const c = 2 * Math.PI * r;
    const p = Math.max(0, Math.min(100, progress || 0));
    return `<div class="ring"><svg viewBox="0 0 120 120">
        <circle cx="60" cy="60" r="${r}" class="ring-bg"/>
        ${p > 0 ? `<circle cx="60" cy="60" r="${r}" class="ring-fg" style="stroke:${color}"
          stroke-dasharray="${(c * p) / 100} ${c}" transform="rotate(-90 60 60)"/>` : ""}
      </svg><div class="ring-inner">${inner}</div></div>`;
  }

  _renderWallTile(p, t) {
    const stateObj = this._state(p, "sensor.printer_state");
    const state = stateObj?.state || "unavailable";
    const printing = PRINTING_STATES.has(state);
    const color = STATE_COLORS[state] || "var(--secondary-text-color)";
    const progress = num(this._state(p, "sensor.progress"));
    const remaining = num(this._state(p, "sensor.remaining_time"));
    const end = this._state(p, "sensor.end_time")?.state;
    const job = this._state(p, "sensor.current_print")?.state;
    const cover = this._state(p, "image.cover")?.attributes?.entity_picture;
    const inner = printing
      ? `${cover ? `<img src="${esc(cover)}" alt="">` : ""}<span class="pct">${Math.round(progress ?? 0)}<small>%</small></span>`
      : `<ha-icon icon="${state === "offline" ? "mdi:printer-3d-off" : "mdi:printer-3d"}"></ha-icon>`;
    const queue = this._state(p, "sensor.printer_queue")?.attributes?.jobs || [];
    const next = queue[0];
    const plate = this._state(p, "binary_sensor.awaiting_plate_clear")?.state === "on";
    const clearBtn = p.one["button.clear_plate"];
    const errors = num(this._state(p, "sensor.hms_errors"));
    const warn =
      this._config.show_filament_check && next && (next.filament_ok === false || next.filament_short)
        ? `<div class="w-banner warn"><ha-icon icon="mdi:alert"></ha-icon>${esc(
            next.filament_ok === false ? `${next.filament_missing.join(", ")} ${t.filament_missing}` : t.filament_short,
          )}</div>`
        : "";
    return `<div class="w-tile" style="--accent:${color}" data-dialog="${esc(p.id)}">
      <div class="w-head"><span class="w-name">${esc(p.name)}</span><span class="chip" style="--chip:${color}">${esc(this._fmt(stateObj))}</span></div>
      ${this._ring(printing ? progress : 0, color, inner)}
      <div class="w-job">${printing && job && !["unknown", "unavailable"].includes(job) ? esc(job) : "&nbsp;"}</div>
      <div class="w-time">${printing && remaining != null ? `${esc(formatMinutes(remaining))} · ${esc(this._time(end))}` : "&nbsp;"}</div>
      ${plate ? `<div class="w-banner plate"><ha-icon icon="mdi:broom"></ha-icon><span>${esc(t.plate)}</span>${
        clearBtn && this._hass.states[clearBtn]?.state !== "unavailable" ? `<button data-press="${esc(clearBtn)}">${esc(t.plate_done)}</button>` : ""
      }</div>` : ""}
      ${errors ? `<div class="w-banner error"><ha-icon icon="mdi:alert"></ha-icon>${errors} ${esc(errors === 1 ? t.error_one : t.errors)}</div>` : ""}
      ${warn}
      ${next ? `<div class="w-next"><span>${esc(t.up_next)}</span> ${esc(next.name || "?")}${colorDots(next.filament_colors)}${
        next.estimated_start ? ` <span class="w-at">${esc(t.approx)} ${esc(this._time(next.estimated_start))}</span>` : ""
      }${queue.length > 1 ? ` <span class="w-more">+${queue.length - 1}</span>` : ""}</div>` : ""}
    </div>`;
  }

  _renderWall(t) {
    const states = this._printers.map((p) => this._state(p, "sensor.printer_state")?.state);
    const printing = states.filter((s) => PRINTING_STATES.has(s)).length;
    const idle = states.filter((s) => s === "idle" || s === "finish").length;
    const waiting = num(this._state(this._hub, "sensor.queue_pending")) ?? 0;
    const farmDone = this._state(this._hub, "sensor.farm_done_at")?.state;
    const clock = new Date().toLocaleTimeString(this._hass.locale?.language || undefined, { hour: "2-digit", minute: "2-digit" });
    const chips = [
      `<span class="w-chip"><ha-icon icon="mdi:printer-3d-nozzle"></ha-icon>${printing} ${esc(t.printing_n)}</span>`,
      `<span class="w-chip"><ha-icon icon="mdi:check-circle-outline"></ha-icon>${idle} ${esc(t.idle_n)}</span>`,
      `<span class="w-chip"><ha-icon icon="mdi:format-list-numbered"></ha-icon>${waiting} ${esc(t.waiting_n)}</span>`,
      farmDone && !["unknown", "unavailable"].includes(farmDone)
        ? `<span class="w-chip"><ha-icon icon="mdi:flag-checkered"></ha-icon>${esc(t.all_done)} ${esc(this._time(farmDone))}</span>`
        : "",
    ].join("");
    const tiles = this._printers.map((p) => this._renderWallTile(p, t)).join("");
    const timeline = this._config.show_timeline ? this._renderTimeline(t, false) : "";
    const queue = this._config.show_queue && this._hub ? this._renderQueue(t) : "";
    return `<div class="w-top"><span class="w-title">${esc(this._config.title || "Bambuddy")}</span>
        <span class="w-chips">${chips}</span><span class="w-clock">${esc(clock)}</span></div>
      <div class="w-grid">${tiles || `<div class="empty pad">${esc(t.no_printers)}</div>`}</div>${timeline}${queue}`;
  }

  // The detail window lives directly under <body>: dashboard containers can
  // clip or offset position:fixed content inside the card.
  _renderDialogHost(t) {
    const html = this._renderDialog(t);
    if (!html) {
      this._dialogHost?.remove();
      this._dialogHost = null;
      return;
    }
    if (!this._dialogHost) {
      this._dialogHost = document.createElement("bambuddy-card-dialog");
      const root = this._dialogHost.attachShadow({ mode: "open" });
      root.addEventListener("click", (ev) => this._onClick(ev));
      document.addEventListener("keydown", (this._onKey ||= (ev) => {
        if (ev.key === "Escape" && this._dialog) {
          this._dialog = null;
          this._render();
        }
      }));
      document.body.appendChild(this._dialogHost);
    }
    this._dialogHost.shadowRoot.innerHTML = `<style>${STYLE}${DIALOG_STYLE}</style>${html}`;
  }

  _renderDialog(t) {
    const p = this._dialog && this._printers.find((x) => x.id === this._dialog);
    if (!p) return "";
    const stateObj = this._state(p, "sensor.printer_state");
    const state = stateObj?.state || "unavailable";
    const color = STATE_COLORS[state] || "var(--secondary-text-color)";
    const printing = PRINTING_STATES.has(state);
    const progress = num(this._state(p, "sensor.progress")) ?? 0;
    const remaining = num(this._state(p, "sensor.remaining_time"));
    const end = this._state(p, "sensor.end_time")?.state;
    const job = this._state(p, "sensor.current_print")?.state;
    const freeAt = this._state(p, "sensor.free_at");
    const schedule = freeAt?.attributes?.schedule || [];
    const jobs = Object.fromEntries((this._state(p, "sensor.printer_queue")?.attributes?.jobs || []).map((j) => [j.id, j]));
    const pending = (this._state(this._hub, "sensor.queue_pending")?.attributes?.jobs || []);
    for (const j of pending) jobs[j.id] ||= j;

    const notifyId = p.one["switch.notify_when_done"];
    const notify = notifyId ? this._hass.states[notifyId] : null;
    const targets = notify?.attributes?.targets || [];
    const notifyRow = notify
      ? `<div class="d-notify">
          <ha-icon icon="${notify.state === "on" ? "mdi:bell-ring" : "mdi:bell-outline"}"></ha-icon>
          <div class="d-notify-text"><div>${esc(t.notify_done)}</div>
            <small>${esc(targets.length ? `${t.notify_to} ${targets.join(", ")}` : t.notify_ha)}</small>
            ${targets.length ? "" : `<small class="hint">${esc(t.notify_hint)}</small>`}</div>
          <button class="switch ${notify.state === "on" ? "on" : ""}" data-switch="${esc(notifyId)}" role="switch"
            aria-checked="${notify.state === "on"}"><span></span></button>
        </div>`
      : "";

    const current = printing
      ? `<div class="d-current">
          <div class="d-job">${esc(job && !["unknown", "unavailable"].includes(job) ? job : "")}</div>
          <div class="bar"><div style="width:${Math.min(100, Math.max(0, progress))}%;background:${color}"></div></div>
          <div class="d-big"><span>${Math.round(progress)} %</span>
            <span>${esc(t.done_at)} <b>${esc(this._time(end))}</b>${remaining != null ? ` · ${esc(t.in_time)} ${esc(formatMinutes(remaining))}` : ""}</span></div>
        </div>`
      : "";

    const freeText =
      freeAt && !["unknown", "unavailable"].includes(freeAt.state)
        ? `${t.free_from} <b>${esc(this._time(freeAt.state, true))}</b>`
        : `<b>${esc(t.free_now)}</b>`;
    const planned = schedule.filter((e) => !e.running);
    const rows = planned.length
      ? planned
          .map((e, i) => {
            const j = jobs[e.id] || {};
            const warn =
              j.filament_ok === false
                ? `<div class="job-warn"><ha-icon icon="mdi:alert"></ha-icon>${esc(`${j.filament_missing.join(", ")} ${t.filament_missing}`)}</div>`
                : j.filament_short
                  ? `<div class="job-warn"><ha-icon icon="mdi:alert"></ha-icon>${esc(t.filament_short)}</div>`
                  : "";
            return `<li><span class="d-when">${esc(this._time(e.start))}${e.end ? `<br><small>– ${esc(this._time(e.end))}</small>` : ""}</span>
              <span class="d-what"><b>${i + 1}. ${esc(e.name || "?")}</b>${colorDots(j.filament_colors)}
                <small>${esc([j.print_time_minutes ? formatMinutes(j.print_time_minutes) : null, j.filament_type, e.predicted ? t.predicted : null].filter(Boolean).join(" · "))}</small>${warn}</span></li>`;
          })
          .join("")
      : `<li class="empty">${esc(t.nothing_planned)}</li>`;

    return `<div class="d-backdrop" data-close="1">
      <div class="d-box" role="dialog" aria-label="${esc(p.name)}" style="--accent:${color}">
        <div class="d-head"><span class="d-title">${esc(p.name)}</span>
          <span class="chip" style="--chip:${color}">${esc(this._fmt(stateObj))}</span>
          <button class="icon" data-close="1" aria-label="${esc(t.close)}"><ha-icon icon="mdi:close"></ha-icon></button></div>
        ${current}
        ${notifyRow}
        <div class="d-free"><ha-icon icon="mdi:clock-check-outline"></ha-icon><span>${freeText}</span></div>
        <div class="d-sub">${esc(t.plan)}</div>
        <ol class="d-plan">${rows}</ol>
        <div class="d-actions"><button data-device="${esc(p.id)}"><ha-icon icon="mdi:format-list-bulleted"></ha-icon>${esc(t.all_entities)}</button></div>
      </div></div>`;
  }

  // ---- interaction ------------------------------------------------------

  _onClick(ev) {
    const el = ev
      .composedPath()
      .find(
        (n) =>
          n.dataset &&
          (n.dataset.close || n.dataset.dialog || n.dataset.switch || n.dataset.device ||
            n.dataset.collapse || n.dataset.press || n.dataset.toggle || n.dataset.more),
      );
    if (!el) return;
    const t = TEXT[lang()];
    if (el.dataset.close) {
      // Only the backdrop itself or the close button, not clicks inside the box.
      if (el.classList.contains("d-backdrop") && ev.target !== el) return;
      this._dialog = null;
      this._render();
    } else if (el.dataset.dialog) {
      this._dialog = el.dataset.dialog;
      this._render();
    } else if (el.dataset.switch) {
      this._call("switch", "toggle", el.dataset.switch);
    } else if (el.dataset.device) {
      this._dialog = null;
      this._render();
      history.pushState(null, "", `/config/devices/device/${el.dataset.device}`);
      window.dispatchEvent(new CustomEvent("location-changed", { detail: { replace: false } }));
    } else if (el.dataset.collapse) {
      this._toggleCollapsed(el.dataset.collapse);
    } else if (el.dataset.press) {
      if (el.dataset.confirm && !window.confirm(t.confirm_stop)) return;
      this._call("button", "press", el.dataset.press);
    } else if (el.dataset.toggle) {
      this._call("light", "toggle", el.dataset.toggle);
    } else if (el.dataset.more) {
      this.dispatchEvent(
        new CustomEvent("hass-more-info", { detail: { entityId: el.dataset.more }, bubbles: true, composed: true }),
      );
    }
  }

  async _call(domain, service, entityId) {
    try {
      await this._hass.callService(domain, service, { entity_id: entityId });
    } catch (err) {
      this.dispatchEvent(
        new CustomEvent("hass-notification", {
          detail: { message: err?.message || String(err) },
          bubbles: true,
          composed: true,
        }),
      );
    }
  }
}

const STYLE = `
  ha-card { padding: 0 0 4px; overflow: hidden; }
  .printers { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 12px; padding: 12px; }
  .printers.single { padding: 0; }
  .printers:not(.single) section.printer { border: 1px solid var(--divider-color); border-radius: 12px;
    border-top: 4px solid var(--accent); background: color-mix(in srgb, var(--accent) 4%, var(--card-background-color, transparent)); }
  .printers.single section.printer { border-top: 4px solid var(--accent); }
  .pad { padding: 12px 16px; }
  .card-title { margin: 0; padding: 12px 16px 0; font-size: 1.25em; font-weight: 500; color: var(--ha-card-header-color, var(--primary-text-color)); }
  section { padding: 12px 16px; }
  .printers + section, .card-title + section { border-top: 1px solid var(--divider-color); }
  [data-collapse] { cursor: pointer; user-select: none; }
  .chevron { --mdc-icon-size: 20px; color: var(--secondary-text-color); }
  .peek { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-weight: 400; color: var(--primary-text-color); }
  .pqueue.collapsed { padding-bottom: 4px; }
  [data-more], [data-press], [data-toggle] { cursor: pointer; }
  .head { display: flex; align-items: center; gap: 8px; }
  .head ha-icon { color: var(--state-icon-color, var(--secondary-text-color)); --mdc-icon-size: 22px; }
  .name { font-weight: 500; font-size: 1.05em; flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .chip { padding: 2px 10px; border-radius: 12px; font-size: 0.85em; font-weight: 500; color: var(--chip);
          background: color-mix(in srgb, var(--chip) 15%, transparent); white-space: nowrap; }
  .count { min-width: 22px; text-align: center; padding: 1px 7px; border-radius: 11px; font-size: 0.85em;
           background: var(--secondary-background-color); color: var(--secondary-text-color); }
  .job { display: flex; gap: 12px; margin-top: 12px; align-items: center; }
  .cover { width: 72px; height: 72px; object-fit: contain; border-radius: 8px; background: var(--secondary-background-color); flex: none; }
  .info { flex: 1; min-width: 0; }
  .title { font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .stage { font-size: 0.85em; color: var(--secondary-text-color); margin-top: 2px; }
  .bar { height: 8px; border-radius: 4px; background: var(--secondary-background-color); margin: 8px 0 6px; overflow: hidden; }
  .bar > div { height: 100%; border-radius: 4px; background: var(--primary-color); transition: width 0.6s ease; }
  .meta { display: flex; flex-wrap: wrap; gap: 4px 14px; font-size: 0.85em; color: var(--secondary-text-color); }
  .meta .pct { color: var(--primary-text-color); font-weight: 500; }
  .meta ha-icon, .pill ha-icon, .hum ha-icon, button ha-icon { --mdc-icon-size: 16px; margin-right: 3px; vertical-align: -3px; }
  .banner { display: flex; align-items: center; gap: 8px; margin-top: 10px; padding: 8px 10px; border-radius: 8px; font-size: 0.9em; }
  .banner span { flex: 1; }
  .banner.warn { background: color-mix(in srgb, var(--warning-color, #ffa000) 15%, transparent); }
  .banner.error { background: color-mix(in srgb, var(--error-color, #db4437) 15%, transparent); color: var(--error-color, #db4437); }
  .pills { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 12px; }
  .pill { padding: 3px 9px; border-radius: 14px; font-size: 0.85em; background: var(--secondary-background-color); white-space: nowrap; }
  .pill.heating ha-icon { color: var(--warning-color, #ffa000); }
  .ams { margin-top: 12px; }
  .spools { display: grid; grid-template-columns: repeat(auto-fill, minmax(58px, 1fr)); gap: 6px; }
  .spool { text-align: center; padding: 6px 2px; border-radius: 8px; border: 2px solid transparent; font-size: 0.78em; min-width: 0; }
  .spool.active { border-color: var(--primary-color); background: color-mix(in srgb, var(--primary-color) 8%, transparent); }
  .spool.empty { opacity: 0.55; }
  .dot { width: 26px; height: 26px; margin: 0 auto 4px; border-radius: 50%; background: var(--spool);
         border: 2px solid var(--divider-color); box-shadow: inset 0 0 0 6px var(--spool), inset 0 0 0 9px var(--card-background-color, #fff); }
  .spool.empty .dot { border-style: dashed; box-shadow: none; }
  .slot { color: var(--secondary-text-color); }
  .fil { font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .rem { color: var(--secondary-text-color); }
  .hums { display: flex; gap: 12px; margin-top: 6px; font-size: 0.85em; color: var(--secondary-text-color); }
  .controls { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 12px; }
  button { font: inherit; font-size: 0.85em; padding: 5px 12px; border-radius: 16px; cursor: pointer;
           border: 1px solid var(--divider-color); background: transparent; color: var(--primary-text-color); }
  button:hover { background: var(--secondary-background-color); }
  button.danger { color: var(--error-color, #db4437); }
  button.on ha-icon { color: var(--warning-color, #ffa000); }
  .banner button { flex: none; }
  .camera { display: block; width: 100%; margin-top: 12px; border-radius: 8px; }
  ol { list-style: none; margin: 8px 0 0; padding: 0; }
  li { display: grid; grid-template-columns: 24px 1fr; column-gap: 6px; padding: 6px 0; }
  li + li { border-top: 1px solid var(--divider-color); }
  .marker { grid-row: span 3; color: var(--secondary-text-color); font-size: 0.9em; padding-top: 1px; }
  .marker ha-icon { --mdc-icon-size: 18px; color: var(--success-color, #43a047); }
  .job-name { font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  li.running .job-name { color: var(--success-color, #43a047); }
  .job-details, .job-wait { font-size: 0.82em; color: var(--secondary-text-color); }
  .job-wait { font-style: italic; }
  .pqueue { margin-top: 12px; padding: 4px 10px 2px; border-radius: 8px; background: var(--secondary-background-color); }
  .pqueue ol { margin-top: 2px; }
  .pqueue li { padding: 4px 0; }
  .subhead { display: flex; align-items: center; gap: 6px; font-size: 0.85em; font-weight: 500; color: var(--secondary-text-color); padding-top: 4px; }
  .subhead .label { flex: none; }
  .pqueue:not(.collapsed) .subhead .label { flex: 1; }
  .subhead ha-icon { --mdc-icon-size: 16px; }
  .pqueue .count { background: var(--card-background-color); }
  .more { margin-top: 6px; font-size: 0.85em; color: var(--primary-color); }
  .empty { color: var(--secondary-text-color); font-size: 0.9em; padding: 8px 0 0; }
  .cdot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-left: 5px; vertical-align: 0;
          border: 1px solid var(--divider-color); }
  .job-warn { font-size: 0.82em; color: var(--warning-color, #ffa000); }
  .job-warn ha-icon { --mdc-icon-size: 14px; margin-right: 3px; vertical-align: -2px; }
  .timeline .head .done { font-size: 0.85em; color: var(--secondary-text-color); white-space: nowrap; }
  .tl { margin-top: 10px; }
  .tl-row { display: flex; align-items: center; gap: 8px; margin: 4px 0; }
  .tl-name { width: 92px; flex: none; font-size: 0.82em; color: var(--secondary-text-color); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .tl-track { position: relative; flex: 1; height: 22px; border-radius: 6px; background: var(--secondary-background-color); overflow: hidden; }
  .axis .tl-track { background: none; height: 16px; overflow: visible; }
  .tick { position: absolute; top: 0; transform: translateX(-50%); font-size: 0.72em; color: var(--secondary-text-color); white-space: nowrap; }
  .seg { position: absolute; top: 2px; bottom: 2px; border-radius: 4px; padding: 0 6px; box-sizing: border-box; font-size: 0.72em; line-height: 18px;
         color: #fff; background: var(--primary-color); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .seg.alt { background: color-mix(in srgb, var(--primary-color) 70%, #000); }
  .seg.running { background: var(--seg); }
  .seg.predicted { background: repeating-linear-gradient(135deg, var(--primary-color) 0 6px, color-mix(in srgb, var(--primary-color) 75%, #fff) 6px 12px); }
  .seg.open { -webkit-mask-image: linear-gradient(90deg, #000 70%, transparent); mask-image: linear-gradient(90deg, #000 70%, transparent); }
  .tl-free { position: absolute; left: 8px; line-height: 22px; font-size: 0.75em; color: var(--secondary-text-color); }
`;

const DIALOG_STYLE = `
  :host { font-family: var(--ha-font-family-body, Roboto, sans-serif); }
  .name ha-icon.info { --mdc-icon-size: 16px; margin-left: 4px; color: var(--secondary-text-color); vertical-align: -2px; }
  [data-dialog] { cursor: pointer; }
  .d-backdrop { position: fixed; inset: 0; z-index: 10; background: rgba(0, 0, 0, 0.45); display: flex; align-items: center;
                justify-content: center; padding: 16px; box-sizing: border-box; }
  .d-box { width: min(520px, 100%); max-height: calc(100vh - 32px); overflow: auto; box-sizing: border-box; padding: 18px 20px;
           border-radius: var(--ha-card-border-radius, 16px); border-top: 6px solid var(--accent);
           background: var(--card-background-color, var(--primary-background-color, #fff)); color: var(--primary-text-color);
           box-shadow: 0 10px 40px rgba(0, 0, 0, 0.35); font-family: var(--ha-font-family-body, inherit); cursor: default; }
  .d-head { display: flex; align-items: center; gap: 10px; }
  .d-title { flex: 1; font-size: 1.3em; font-weight: 500; }
  button.icon { border: none; padding: 4px; border-radius: 50%; }
  .d-current { margin-top: 14px; }
  .d-job { font-weight: 500; }
  .d-big { display: flex; justify-content: space-between; gap: 10px; flex-wrap: wrap; color: var(--secondary-text-color); }
  .d-big span:first-child { font-size: 1.4em; color: var(--primary-text-color); font-weight: 500; }
  .d-big b { color: var(--primary-text-color); }
  .d-notify { display: flex; align-items: center; gap: 12px; margin-top: 16px; padding: 12px; border-radius: 12px;
              background: var(--secondary-background-color); }
  .d-notify > ha-icon { color: var(--warning-color, #ffa000); }
  .d-notify-text { flex: 1; min-width: 0; }
  .d-notify-text small { display: block; color: var(--secondary-text-color); }
  .d-notify-text small.hint { font-style: italic; }
  button.switch { position: relative; width: 44px; height: 24px; padding: 0; border-radius: 12px; border: none;
                  background: var(--disabled-color, #bdbdbd); flex: none; }
  button.switch span { position: absolute; top: 3px; left: 3px; width: 18px; height: 18px; border-radius: 50%; background: #fff;
                       transition: left 0.2s; }
  button.switch.on { background: var(--primary-color); }
  button.switch.on span { left: 23px; }
  .d-free { display: flex; align-items: center; gap: 8px; margin-top: 16px; }
  .d-free ha-icon { color: var(--secondary-text-color); }
  .d-sub { margin-top: 16px; font-size: 0.85em; font-weight: 500; color: var(--secondary-text-color); text-transform: uppercase; letter-spacing: 0.04em; }
  .d-plan { list-style: none; margin: 6px 0 0; padding: 0; }
  .d-plan li { display: flex; gap: 12px; padding: 8px 0; }
  .d-plan li + li { border-top: 1px solid var(--divider-color); }
  .d-when { width: 64px; flex: none; font-variant-numeric: tabular-nums; font-weight: 500; }
  .d-when small { color: var(--secondary-text-color); font-weight: 400; }
  .d-what { flex: 1; min-width: 0; }
  .d-what small { display: block; color: var(--secondary-text-color); }
  .d-actions { margin-top: 16px; display: flex; justify-content: flex-end; }
`;

const WALL_STYLE = `
  ha-card.wall { padding: 16px; font-size: 1.05em; }
  .w-top { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 14px; }
  .w-title { font-size: 1.5em; font-weight: 500; }
  .w-chips { display: flex; gap: 8px; flex-wrap: wrap; flex: 1; }
  .w-chip { display: inline-flex; align-items: center; gap: 4px; padding: 4px 12px; border-radius: 16px;
            background: var(--secondary-background-color); font-size: 0.9em; }
  .w-chip ha-icon { --mdc-icon-size: 18px; color: var(--secondary-text-color); }
  .w-clock { font-size: 2em; font-weight: 300; font-variant-numeric: tabular-nums; }
  .w-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 14px; }
  .w-tile { border-radius: 16px; padding: 14px; border: 1px solid var(--divider-color); border-top: 6px solid var(--accent);
            background: color-mix(in srgb, var(--accent) 5%, var(--card-background-color, transparent)); text-align: center; cursor: pointer; }
  .w-head { display: flex; align-items: center; gap: 8px; text-align: left; }
  .w-name { flex: 1; font-size: 1.25em; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .ring { position: relative; width: min(180px, 70%); aspect-ratio: 1; margin: 12px auto 8px; }
  .ring svg { width: 100%; height: 100%; }
  .ring-bg { fill: none; stroke: var(--secondary-background-color); stroke-width: 10; }
  .ring-fg { fill: none; stroke-width: 10; stroke-linecap: round; transition: stroke-dasharray 0.8s ease; }
  .ring-inner { position: absolute; inset: 18%; border-radius: 50%; overflow: hidden; display: flex; align-items: center; justify-content: center; }
  .ring-inner img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: contain; opacity: 0.35; }
  .ring-inner .pct { position: relative; font-size: 2.6em; font-weight: 500; font-variant-numeric: tabular-nums; }
  .ring-inner .pct small { font-size: 0.45em; margin-left: 2px; }
  .ring-inner ha-icon { --mdc-icon-size: 56px; color: var(--secondary-text-color); }
  .w-job { font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .w-time { color: var(--secondary-text-color); font-variant-numeric: tabular-nums; margin-top: 2px; }
  .w-banner { display: flex; align-items: center; gap: 6px; margin-top: 10px; padding: 8px 10px; border-radius: 10px; font-size: 0.9em; text-align: left; }
  .w-banner span { flex: 1; }
  .w-banner ha-icon { --mdc-icon-size: 18px; flex: none; }
  .w-banner.plate { background: color-mix(in srgb, var(--warning-color, #ffa000) 18%, transparent); }
  .w-banner.warn { background: color-mix(in srgb, var(--warning-color, #ffa000) 12%, transparent); color: var(--warning-color, #ffa000); }
  .w-banner.error { background: color-mix(in srgb, var(--error-color, #db4437) 15%, transparent); color: var(--error-color, #db4437); }
  .w-banner button { font-size: 1em; padding: 8px 16px; }
  .w-next { margin-top: 10px; font-size: 0.9em; text-align: left; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .w-next > span:first-child, .w-at, .w-more { color: var(--secondary-text-color); }
  .wall section { padding: 14px 4px 0; border-top: none; }
  .wall .tl-name { width: 110px; font-size: 0.9em; }
  .wall .tl-track { height: 28px; }
  .wall .seg { line-height: 24px; font-size: 0.8em; }
`;

if (!customElements.get("bambuddy-card")) {
  customElements.define("bambuddy-card", BambuddyCard);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "bambuddy-card",
    name: "Bambuddy",
    description: "Drucker, AMS und Warteschlange aus Bambuddy auf einen Blick.",
    preview: true,
    documentationURL: "https://github.com/Notch001/ha-bambuddy-integration",
  });
  console.info(`%c BAMBUDDY-CARD %c ${CARD_VERSION} `, "background:#00ae42;color:#fff;font-weight:700", "");
}
