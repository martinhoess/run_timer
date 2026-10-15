// run_timer: panel in the more-info dialog of a managed entity (experiment).
//
// Home Assistant has no extension point for the more-info dialog. This script
// looks for the dialog in the frontend's DOM and appends a panel; if the
// frontend changes its structure, the panel silently stays away.
// Path checked against frontend 20260930.4:
// home-assistant > ha-more-info-dialog > ha-adaptive-dialog > ha-more-info-info > .content

(() => {
  if (window.__runTimerPanel) return;
  window.__runTimerPanel = true;

  const PANEL = "run-timer-panel";
  const TEXT = {
    en: {
      next_start: "Next start", next_stop: "Next stop", none: "–",
      schedule_start: "Schedule start", schedule_stop: "Schedule stop",
      set: "Set", clear: "Clear", stop_timer: "Drop timer",
      off_in: (m) => (m < 60 ? `off in ${m} min` : `off in ${m / 60} h`),
      in: (t) => `in ${t}`, ago: (t) => `${t} ago`,
    },
    de: {
      next_start: "Nächstes An", next_stop: "Nächstes Aus", none: "–",
      schedule_start: "Schaltzeit an", schedule_stop: "Schaltzeit aus",
      set: "Setzen", clear: "Löschen", stop_timer: "Timer weg",
      off_in: (m) => (m < 60 ? `aus in ${m} min` : `aus in ${m / 60} h`),
      in: (t) => `in ${t}`, ago: (t) => `vor ${t}`,
    },
  };

  let managed = null; // {entity_id: {translation_key: entity_id}}
  let managedAt = 0;
  let lastEntity = null; // entity of the open dialog at the last check
  let pending = null; // running run_timer/list call

  const ha = () => document.querySelector("home-assistant");
  const hass = () => ha()?.hass;
  const text = () => (hass()?.locale?.language?.startsWith("de") ? TEXT.de : TEXT.en);

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

  function relative(iso) {
    const ms = new Date(iso) - Date.now();
    const min = Math.round(Math.abs(ms) / 60000);
    const span = min < 60 ? `${min} min` : `${Math.floor(min / 60)} h${min % 60 ? ` ${min % 60} min` : ""}`;
    return ms >= 0 ? text().in(span) : text().ago(span);
  }

  function clock(iso) {
    const h = hass();
    return new Date(iso).toLocaleTimeString(h?.locale?.language || undefined, {
      hour: "2-digit", minute: "2-digit", timeZone: h?.config?.time_zone,
    });
  }

  function call(service, data) {
    // The frontend shows the error as a toast and rethrows it; keep the console clean.
    return hass().callService("run_timer", service, data).catch(() => {});
  }

  function setTime(entityId, value) {
    return hass()
      .callService("time", "set_value", { entity_id: entityId, time: `${value}:00` })
      .catch(() => {});
  }

  function build(entityId, ents) {
    const t = text();
    const panel = document.createElement("div");
    panel.id = PANEL;
    panel.dataset.entityId = entityId;
    const root = panel.attachShadow({ mode: "open" });
    root.innerHTML = `
      <style>
        :host { display: block; margin-top: var(--ha-space-6, 24px); }
        .box { border-top: 1px solid var(--divider-color); padding-top: 16px; display: grid; gap: 14px; }
        .rows { display: grid; grid-template-columns: auto 1fr; gap: 6px 16px; font-size: 14px; }
        .label { color: var(--secondary-text-color); }
        .value { color: var(--primary-text-color); text-align: end; font-variant-numeric: tabular-nums; }
        .chips { display: flex; flex-wrap: wrap; gap: 8px; }
        button {
          font: inherit; font-size: 13px; color: var(--primary-text-color); cursor: pointer;
          background: var(--secondary-background-color); border: 1px solid var(--divider-color);
          border-radius: 18px; padding: 6px 12px;
        }
        button:hover { border-color: var(--primary-color); }
        button:focus-visible, input:focus-visible { outline: 2px solid var(--primary-color); outline-offset: 2px; }
        .times { display: grid; grid-template-columns: auto 1fr auto auto; gap: 8px 10px; align-items: center; font-size: 14px; }
        input[type="time"] {
          font: inherit; color: var(--primary-text-color); background: var(--secondary-background-color);
          border: 1px solid var(--divider-color); border-radius: 8px; padding: 5px 8px;
          color-scheme: var(--run-timer-scheme, light dark);
        }
      </style>
      <div class="box">
        <div class="rows">
          <span class="label">${t.next_start}</span><span class="value" data-k="on_time"></span>
          <span class="label">${t.next_stop}</span><span class="value" data-k="off_time"></span>
        </div>
        <div class="chips">
          <button data-extend="-15">−15</button>
          <button data-extend="15">+15</button>
          <button data-off-in="30">${t.off_in(30)}</button>
          <button data-off-in="60">${t.off_in(60)}</button>
          <button data-off-in="120">${t.off_in(120)}</button>
          <button data-cancel="off">${t.stop_timer}</button>
        </div>
        <div class="times">
          <span class="label">${t.schedule_start}</span><input type="time" data-time="switch_on_at">
          <button data-set="switch_on_at">${t.set}</button><button data-clear="on">${t.clear}</button>
          <span class="label">${t.schedule_stop}</span><input type="time" data-time="switch_off_at">
          <button data-set="switch_off_at">${t.set}</button><button data-clear="off">${t.clear}</button>
        </div>
      </div>`;
    root.querySelectorAll("[data-extend]").forEach((b) =>
      b.addEventListener("click", () => call("extend", { entity_id: entityId, minutes: Number(b.dataset.extend) })));
    root.querySelectorAll("[data-off-in]").forEach((b) =>
      b.addEventListener("click", () => call("off_in", { entity_id: entityId, minutes: Number(b.dataset.offIn) })));
    root.querySelectorAll("[data-cancel]").forEach((b) =>
      b.addEventListener("click", () => call("cancel", { entity_id: entityId, what: b.dataset.cancel })));
    root.querySelectorAll("[data-clear]").forEach((b) =>
      b.addEventListener("click", () => {
        const field = b.dataset.clear === "on" ? "switch_on_at" : "switch_off_at";
        delete root.querySelector(`[data-time="${field}"]`).dataset.dirty;
        call("cancel", { entity_id: entityId, what: b.dataset.clear });
      }));
    root.querySelectorAll("[data-time]").forEach((input) =>
      input.addEventListener("input", () => { input.dataset.dirty = "1"; }));
    root.querySelectorAll("[data-set]").forEach((b) =>
      b.addEventListener("click", () => {
        const input = root.querySelector(`[data-time="${b.dataset.set}"]`);
        delete input.dataset.dirty;
        if (input.value) setTime(ents[b.dataset.set], input.value);
      }));
    panel._update = () => update(panel, ents);
    return panel;
  }

  function update(panel, ents) {
    const h = hass();
    if (!h) return;
    const root = panel.shadowRoot;
    panel.style.setProperty("--run-timer-scheme", h.themes?.darkMode ? "dark" : "light");
    for (const key of ["on_time", "off_time"]) {
      const state = h.states[ents[key]]?.state;
      const valid = state && !["unknown", "unavailable"].includes(state);
      root.querySelector(`[data-k="${key}"]`).textContent = valid ? `${clock(state)} · ${relative(state)}` : text().none;
    }
    for (const key of ["switch_on_at", "switch_off_at"]) {
      const input = root.querySelector(`[data-time="${key}"]`);
      if (input.dataset.dirty) continue; // typed but not set yet
      const state = h.states[ents[key]]?.state;
      input.value = state && !["unknown", "unavailable"].includes(state) ? state.slice(0, 5) : "";
    }
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

  setInterval(() => { tick().catch(() => {}); }, 500);
})();
