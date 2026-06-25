const zonesEl = document.querySelector("#zones");
const statusEl = document.querySelector("#status");
const cameraTotalEl = document.querySelector("#camera-total");
const staleTotalEl = document.querySelector("#stale-total");
const zoneTotalEl = document.querySelector("#zone-total");
const emptyTemplate = document.querySelector("#empty-template");

function text(value, fallback = "none") {
  if (value === null || value === undefined || value === "") {
    return fallback;
  }
  return String(value);
}

function renderChips(items, className = "") {
  if (!items || items.length === 0) {
    return '<span class="chip">none</span>';
  }
  return items.map((item) => `<span class="chip ${className}">${text(item)}</span>`).join("");
}

function renderObjectCounts(counts) {
  const entries = Object.entries(counts || {});
  if (entries.length === 0) {
    return '<span class="chip">quiet</span>';
  }
  return entries.map(([label, count]) => `<span class="chip">${count} ${label}</span>`).join("");
}

function renderCamera(camera) {
  const classes = ["camera"];
  if (camera.stale) classes.push("stale");
  if (camera.error) classes.push("error");
  const age = Number.isFinite(camera.age_seconds) ? `${Math.round(camera.age_seconds)}s ago` : "unknown age";
  const state = camera.error ? "error" : camera.stale ? "stale" : "fresh";
  const summary = camera.error || camera.scene_summary || "No scene summary yet.";

  return `
    <article class="${classes.join(" ")}">
      <div class="camera-title">
        <span>${camera.camera_id}</span>
        <span>${state} · ${age}</span>
      </div>
      <p>${summary}</p>
      <div class="chips">${renderObjectCounts(camera.object_counts)}</div>
    </article>
  `;
}

function renderZone(zone) {
  const risks = zone.risks || [];
  const cameras = zone.cameras_detail || [];
  return `
    <section class="zone">
      <div class="zone-header">
        <div>
          <h2>${zone.zone}</h2>
          <p class="summary">${zone.summary || "No summary yet."}</p>
        </div>
        <div class="muted">${zone.camera_count || 0} cameras</div>
      </div>
      <h3>Objects</h3>
      <div class="chips">${renderObjectCounts(zone.object_counts)}</div>
      <h3>Risks</h3>
      <div class="chips">${renderChips(risks, "risk")}</div>
      <h3>Cameras</h3>
      <div class="camera-list">${cameras.map(renderCamera).join("")}</div>
    </section>
  `;
}

function renderEmpty() {
  zonesEl.replaceChildren(emptyTemplate.content.cloneNode(true));
}

function renderArea(area) {
  const zones = area.zones || [];
  cameraTotalEl.textContent = area.camera_total || 0;
  staleTotalEl.textContent = area.stale_camera_count || 0;
  zoneTotalEl.textContent = zones.length;
  statusEl.textContent = `Last refreshed ${new Date().toLocaleTimeString()}`;

  if (zones.length === 0) {
    renderEmpty();
    return;
  }
  zonesEl.innerHTML = zones.map(renderZone).join("");
}

async function refresh() {
  try {
    const response = await fetch("/area", { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`GET /area returned ${response.status}`);
    }
    renderArea(await response.json());
  } catch (error) {
    statusEl.textContent = `Dashboard refresh failed: ${error.message}`;
  }
}

refresh();
setInterval(refresh, 5000);
