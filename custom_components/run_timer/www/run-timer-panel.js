// run_timer: panel in the more-info dialog of a managed entity.
//
// Home Assistant has no extension point for the more-info dialog. This script
// looks for the dialog in the frontend's DOM and appends a panel; if the
// frontend changes its structure, the panel silently stays away.
// Path checked against frontend 20260930.4:
// home-assistant > ha-more-info-dialog > ha-adaptive-dialog > ha-more-info-info > .content
//
// Only parts the dialog itself loads are used (ha-button, ha-icon-button);
// lazily loaded ones such as ha-time-input are not reliably defined there.

(() => {
  if (window.__runTimerPanel) return;
  window.__runTimerPanel = true;

  const PANEL = "run-timer-panel";
  const CLOSE = "M19,6.41L17.59,5L12,10.59L6.41,5L5,6.41L10.59,12L5,17.59L6.41,19L12,13.41L17.59,19L19,17.59L13.41,12L19,6.41Z";
  const TEXT = {
    en: {
      start: "Start", stop: "Stop", clear: "Clear",
      off_in: (m) => (m < 60 ? `Off in ${m} min` : `Off in ${m / 60} h`),
    },
    de: {
      start: "Start", stop: "Stopp", clear: "Löschen",
      off_in: (m) => (m < 60 ? `Aus in ${m} min` : `Aus in ${m / 60} h`),
    },
  };

  let managed = null; // {entity_id: {translation_key: entity_id}}
  let managedAt = 0;
  let lastEntity = null; // entity of the open dialog at the last check
  let pending = null; // running run_timer/list call
  const warned = new Set();
  const warn = (what, err) => {
    if (warned.has(what)) return;
    warned.add(what);
    console.warn(`[run_timer] ${what}:`, err);
  };

  const ha = () => document.querySelector("home-assistant");
  const hass = () => ha()?.hass;
  const lang = () => hass()?.locale?.language || "en";
  const text = () => (lang().startsWith("de") ? TEXT.de : TEXT.en);

  async function loadManaged(force = false) {
    const h = hass();
    if (!h || (!force && managed && Date.now() - managedAt < 30000)) return managed;
    pending ??= h
      .callWS({ type: "run_timer/list" })
      .catch(() => ({}))
      .then((result) => {
        managed = result;
        managedAt = Date.now();
      })
      .finally(() => {
        pending = null;
      });
    await pending;
    return managed;
  }

  function findDialog() {
    const dialog = ha()?.shadowRoot?.querySelector("ha-more-info-dialog");
    const frame = dialog?.shadowRoot?.querySelector("ha-adaptive-dialog, ha-dialog");
    const info = frame?.querySelector("ha-more-info-info");
    const content = info?.shadowRoot?.querySelector(".content");
    return content && info.entityId ? { content, entityId: info.entityId } : null;
  }

  // The frontend shows a failed call as a toast and rethrows it; keep the console clean.
  const call = (service, data) => hass().callService("run_timer", service, data).catch(() => {});

  function timestamp(entityId) {
    const state = hass()?.states[entityId]?.state;
    const date = state && !["unknown", "unavailable"].includes(state) ? new Date(state) : null;
    return date && !Number.isNaN(date.getTime()) ? date : null;
  }

  function clock(date) {
    const h = hass();
    return date.toLocaleTimeString("en-GB", {
      hour: "2-digit", minute: "2-digit", hourCycle: "h23", timeZone: h?.config?.time_zone,
    });
  }

  function relative(date) {
    const minutes = Math.round((date - Date.now()) / 60000);
    const format = new Intl.RelativeTimeFormat(lang(), { numeric: "auto" });
    const abs = Math.abs(minutes);
    if (abs < 60) return format.format(minutes, "minute");
    if (abs < 48 * 60) {
      const rest = abs % 60;
      return minutes > 0 && rest && abs < 600
        ? `${format.format(Math.trunc(minutes / 60), "hour")} ${new Intl.NumberFormat(lang()).format(rest)} min`
        : format.format(Math.round(minutes / 60), "hour");
    }
    return new Intl.RelativeTimeFormat(lang(), { numeric: "always" }).format(Math.round(minutes / 1440), "day");
  }

  // "7", "715", "0715", "7:15", "07.15" -> "07:15"; null if not a time of day.
  function parseTime(value) {
    const m = value.trim().match(/^(\d{1,2})(?:[:.]?(\d{2}))?$/);
    if (!m) return null;
    const hh = Number(m[1]);
    const mm = Number(m[2] ?? 0);
    return hh < 24 && mm < 60 ? `${String(hh).padStart(2, "0")}:${String(mm).padStart(2, "0")}` : null;
  }

  // What a line shows: the timestamp sensor, else (stop while off) the fixed off time of day.
  function shown({ sensor, fixed }) {
    const date = timestamp(sensor);
    if (date) return { date, time: clock(date) };
    const state = fixed && hass()?.states[fixed]?.state;
    return { date: null, time: state && /^\d{2}:\d{2}/.test(state) ? state.slice(0, 5) : "" };
  }

  function button(label, onClick) {
    const b = document.createElement("ha-button");
    b.setAttribute("appearance", "filled");
    b.setAttribute("variant", "neutral");
    b.setAttribute("size", "s");
    b.textContent = label;
    b.addEventListener("click", onClick);
    return b;
  }

  function build(entityId, ents) {
    const t = text();
    const panel = document.createElement("div");
    panel.id = PANEL;
    panel.dataset.entityId = entityId;
    const root = panel.attachShadow({ mode: "open" });
    root.innerHTML = `
      <style>
        :host { display: block; margin-top: var(--ha-space-4, 16px); }
        .box { border-top: 1px solid var(--divider-color); padding-top: var(--ha-space-3, 12px);
               display: grid; grid-template-columns: auto auto 1fr auto; align-items: center;
               column-gap: var(--ha-space-3, 12px); row-gap: var(--ha-space-1, 4px); }
        .label { color: var(--primary-text-color); }
        .rel { color: var(--secondary-text-color); font-size: var(--ha-font-size-s, 12px); }
        input {
          width: 5ch; font: inherit; font-variant-numeric: tabular-nums; text-align: center;
          color: var(--primary-text-color); background: var(--input-fill-color, var(--secondary-background-color));
          border: none; border-bottom: 1px solid var(--input-idle-line-color, var(--divider-color));
          border-radius: var(--ha-border-radius-sm, 4px) var(--ha-border-radius-sm, 4px) 0 0;
          padding: 6px 8px;
        }
        input::placeholder { color: var(--secondary-text-color); }
        input:focus { outline: none; border-bottom: 2px solid var(--primary-color); padding-bottom: 5px; }
        .chips { grid-column: 1 / -1; display: flex; flex-wrap: wrap; gap: var(--ha-space-2, 8px);
                 padding-top: var(--ha-space-2, 8px); }
      </style>
      <div class="box"></div>`;
    const box = root.querySelector(".box");
    const lines = [];
    for (const [label, sensor, fixed, setService, what] of [
      [t.start, ents.on_time, null, "on_at", "on"],
      [t.stop, ents.off_time, ents.switch_off_at, "off_at", "off"],
    ]) {
      const name = document.createElement("span");
      name.className = "label";
      name.textContent = label;
      const input = document.createElement("input");
      input.inputMode = "numeric";
      input.placeholder = "--:--";
      input.maxLength = 5;
      input.setAttribute("aria-label", label);
      const rel = document.createElement("span");
      rel.className = "rel";
      const clear = document.createElement("ha-icon-button");
      clear.path = CLOSE;
      clear.label = `${t.clear}: ${label}`;
      clear.addEventListener("click", () => call("cancel", { entity_id: entityId, what }));
      const line = { sensor, fixed, input, rel, clear };
      const commit = () => {
        const at = parseTime(input.value);
        // Same time of day within the next 24 h: nothing to change.
        const { date, time } = shown(line);
        const same = time === at && (!date || date - Date.now() < 86400000);
        if (at && !same) call(setService, { entity_id: entityId, at });
        update();
      };
      input.addEventListener("keydown", (ev) => {
        if (ev.key === "Enter") input.blur();
        if (ev.key === "Escape") {
          ev.preventDefault(); // keep the dialog open
          ev.stopPropagation();
          input.value = shown(line).time; // before blur, so no change event fires
          input.blur();
        }
      });
      input.addEventListener("change", commit);
      box.append(name, input, rel, clear);
      lines.push(line);
    }
    const chips = document.createElement("div");
    chips.className = "chips";
    chips.append(
      button("−15", () => call("extend", { entity_id: entityId, minutes: -15 })),
      button("+15", () => call("extend", { entity_id: entityId, minutes: 15 })),
      ...[30, 60, 120].map((m) => button(t.off_in(m), () => call("off_in", { entity_id: entityId, minutes: m }))),
    );
    box.append(chips);
    function update() {
      for (const line of lines) {
        const { date, time } = shown(line);
        if (root.activeElement !== line.input) line.input.value = time;
        line.rel.textContent = date ? relative(date) : "";
        line.clear.style.visibility = time ? "visible" : "hidden";
      }
    }
    panel._update = update;
    return panel;
  }

  // ponytail: polling every 500 ms instead of observing several shadow roots;
  // a handful of querySelector calls, switch to MutationObserver if it ever shows up in profiles.
  async function tick() {
    const found = findDialog();
    if (!found) {
      lastEntity = null;
      return;
    }
    const { content, entityId } = found;
    const opened = entityId !== lastEntity;
    lastEntity = entityId;
    const existing = content.querySelector(`#${PANEL}`);
    if (existing && existing.dataset.entityId === entityId) {
      existing._update();
      return;
    }
    existing?.remove();
    const list = await loadManaged(opened);
    const ents = list?.[entityId];
    if (!ents || content.querySelector(`#${PANEL}`)) return;
    const panel = build(entityId, ents);
    content.appendChild(panel);
    panel._update();
  }

  setInterval(() => { tick().catch((err) => warn("panel failed", err)); }, 500);
})();
