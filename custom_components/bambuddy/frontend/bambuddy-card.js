/*
 * Bambuddy dashboard card for Home Assistant.
 *
 * Shipped and registered by the Bambuddy integration; no separate install.
 * Finds the integration's entities by their translation keys, so it works
 * without any configuration:  type: custom:bambuddy-card
 */

const CARD_VERSION = "0.8.0";

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
          name: "printers",
          selector: { device: { multiple: true, filter: { integration: "bambuddy", manufacturer: "Bambu Lab" } } },
        },
        {
          type: "grid",
          name: "",
          schema: ["show_temperatures", "show_ams", "show_controls", "show_camera", "show_printer_queue", "show_queue", "collapse_queue"].map((name) => ({
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
    return { columns: 12, min_columns: 6 };
  }

  connectedCallback() {
    if (!this.shadowRoot) {
      this.attachShadow({ mode: "open" });
      this.shadowRoot.addEventListener("click", (ev) => this._onClick(ev));
    }
    if (this._hass) this._update();
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

  _fmt(stateObj) {
    if (!stateObj) return "";
    return this._hass.formatEntityState ? this._hass.formatEntityState(stateObj) : stateObj.state;
  }

  // ---- rendering --------------------------------------------------------

  _render() {
    const t = TEXT[lang()];
    const body = this._printers.length
      ? `<div class="printers${this._printers.length === 1 ? " single" : ""}">${this._printers.map((p) => this._renderPrinter(p, t)).join("")}</div>`
      : `<div class="empty pad">${esc(t.no_printers)}</div>`;
    const queue = this._config.show_queue && this._hub ? this._renderQueue(t) : "";
    const title = this._config.title ? `<h1 class="card-title">${esc(this._config.title)}</h1>` : "";
    this.shadowRoot.innerHTML = `<style>${STYLE}</style><ha-card>${title}${body}${queue}</ha-card>`;
  }

  _renderPrinter(p, t) {
    const stateObj = this._state(p, "sensor.printer_state");
    const state = stateObj?.state || "unavailable";
    const printing = PRINTING_STATES.has(state);
    const color = STATE_COLORS[state] || "var(--secondary-text-color)";

    let html = `<section class="printer" style="--accent:${color}">
      <div class="head">
        <ha-icon icon="mdi:printer-3d"></ha-icon>
        <span class="name" data-more="${esc(p.one["sensor.printer_state"])}">${esc(p.name)}</span>
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
    ].filter(Boolean);
    return `<li class="${cls}">
      <span class="marker">${marker}</span>
      <span class="job-name">${esc(job.name || "?")}</span>
      ${details.length ? `<span class="job-details">${esc(details.join(" · "))}</span>` : ""}
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

  // ---- interaction ------------------------------------------------------

  _onClick(ev) {
    const el = ev
      .composedPath()
      .find((n) => n.dataset && (n.dataset.collapse || n.dataset.press || n.dataset.toggle || n.dataset.more));
    if (!el) return;
    const t = TEXT[lang()];
    if (el.dataset.collapse) {
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
