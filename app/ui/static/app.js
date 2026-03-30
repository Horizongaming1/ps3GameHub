const state = {
  games: [],
  targets: [],
  jobs: [],
  health: null,
};

const els = {
  scanBtn: document.getElementById("scanBtn"),
  refreshAllBtn: document.getElementById("refreshAllBtn"),
  hideAppleDouble: document.getElementById("hideAppleDouble"),
  gamesTableBody: document.getElementById("gamesTableBody"),
  targetsTableBody: document.getElementById("targetsTableBody"),
  jobsTableBody: document.getElementById("jobsTableBody"),
  healthGrid: document.getElementById("healthGrid"),
  lastUpdated: document.getElementById("lastUpdated"),
  toast: document.getElementById("toast"),
  targetForm: document.getElementById("targetForm"),
  jobForm: document.getElementById("jobForm"),
  jobGameId: document.getElementById("jobGameId"),
  jobTargetId: document.getElementById("jobTargetId"),
  jobAutoMount: document.getElementById("jobAutoMount"),
};

async function apiFetch(path, options = {}) {
  const response = await fetch(path, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  const isJson = response.headers.get("content-type")?.includes("application/json");
  const payload = isJson ? await response.json() : null;

  if (!response.ok) {
    const message = payload?.message || payload?.detail || `HTTP ${response.status}`;
    throw new Error(message);
  }

  return payload;
}

function showToast(message, type = "info") {
  els.toast.textContent = message;
  els.toast.className = `toast ${type === "error" ? "error" : ""}`;
  els.toast.classList.remove("hidden");
  setTimeout(() => els.toast.classList.add("hidden"), 4000);
}

function formatBytes(bytes) {
  if (bytes == null || Number.isNaN(bytes)) {
    return "-";
  }
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = Number(bytes);
  let idx = 0;
  while (value >= 1024 && idx < units.length - 1) {
    value /= 1024;
    idx += 1;
  }
  return `${value.toFixed(value >= 10 || idx === 0 ? 0 : 1)} ${units[idx]}`;
}

function formatPercent(value) {
  return `${Number(value || 0).toFixed(1)}%`;
}

function renderHealth() {
  if (!state.health) {
    return;
  }

  const cards = [
    { label: "Gesamt", value: state.health.status },
    { label: "API", value: state.health.api },
    { label: "Datenbank", value: state.health.database },
    { label: "Worker", value: state.health.worker.thread_alive ? "alive" : "down" },
    { label: "Aktiver Job", value: state.health.worker.current_job_id ?? "-" },
  ];

  els.healthGrid.innerHTML = cards
    .map(
      (item) => `
      <div class="health-card">
        <strong>${item.label}</strong>
        <span>${item.value}</span>
      </div>
    `
    )
    .join("");

  els.lastUpdated.textContent = `Letztes Update: ${new Date().toLocaleString("de-DE")}`;
}

function renderGames() {
  let games = [...state.games];
  if (els.hideAppleDouble.checked) {
    games = games.filter((g) => !g.filename.startsWith("._"));
  }

  els.gamesTableBody.innerHTML = games
    .map(
      (game) => `
      <tr>
        <td>${game.id}</td>
        <td title="${game.full_path}">${game.filename}</td>
        <td>${game.platform_guess}</td>
        <td>${game.title_guess}</td>
        <td>${formatBytes(game.size_bytes)}</td>
        <td><button class="btn btn-secondary btn-small" data-select-game="${game.id}">Für Job wählen</button></td>
      </tr>
    `
    )
    .join("");

  if (!games.length) {
    els.gamesTableBody.innerHTML = `<tr><td colspan="6" class="muted">Keine Spiele gefunden.</td></tr>`;
  }

  const gameSelect = els.jobGameId;
  const selected = gameSelect.value;
  gameSelect.innerHTML = games
    .map((g) => `<option value="${g.id}">#${g.id} - ${g.title_guess || g.filename}</option>`)
    .join("");

  if (selected) {
    gameSelect.value = selected;
  }
}

function capacityEditor(target) {
  const total = target.capacity_total_bytes || 0;
  const reserved = target.capacity_reserved_bytes || 0;
  const used = target.capacity_used_bytes_estimate || 0;
  const free = Math.max(0, total - reserved - used);

  return `
    <div class="capacity-editor" data-capacity-target="${target.id}">
      <div class="muted">frei ${formatBytes(free)}</div>
      <input type="number" min="0" data-field="total_bytes" value="${total}" />
      <input type="number" min="0" data-field="reserved_bytes" value="${reserved}" />
      <input type="number" min="0" data-field="used_bytes_estimate" value="${used}" />
      <button class="btn btn-secondary btn-small" data-save-capacity="${target.id}">Speichern</button>
    </div>
  `;
}

function renderTargets() {
  els.targetsTableBody.innerHTML = state.targets
    .map(
      (target) => `
      <tr>
        <td>${target.id}</td>
        <td>${target.name}</td>
        <td>${target.ip_address}</td>
        <td>${target.ftp_port}</td>
        <td>${target.target_path}</td>
        <td>${capacityEditor(target)}</td>
      </tr>
    `
    )
    .join("");

  if (!state.targets.length) {
    els.targetsTableBody.innerHTML = `<tr><td colspan="6" class="muted">Noch keine Targets vorhanden.</td></tr>`;
  }

  const targetSelect = els.jobTargetId;
  const selected = targetSelect.value;
  targetSelect.innerHTML = state.targets
    .map((t) => `<option value="${t.id}">#${t.id} - ${t.name} (${t.ip_address})</option>`)
    .join("");

  if (selected) {
    targetSelect.value = selected;
  }
}

function renderJobs() {
  els.jobsTableBody.innerHTML = state.jobs
    .map(
      (job) => `
      <tr>
        <td>${job.id}</td>
        <td><span class="badge ${job.status}">${job.status}</span></td>
        <td>${job.game.filename}</td>
        <td>${job.target.name}</td>
        <td>${formatPercent(job.progress_percent)}</td>
        <td>${formatBytes(job.transferred_bytes)} / ${formatBytes(job.total_bytes)}</td>
        <td class="muted">${job.error_message || "-"}</td>
        <td>
          ${job.status === "queued" || job.status === "running"
            ? `<button class="btn btn-danger btn-small" data-cancel-job="${job.id}">Abbrechen</button>`
            : "-"}
        </td>
      </tr>
    `
    )
    .join("");

  if (!state.jobs.length) {
    els.jobsTableBody.innerHTML = `<tr><td colspan="8" class="muted">Noch keine Jobs vorhanden.</td></tr>`;
  }
}

async function loadHealth() {
  state.health = await apiFetch("/health");
  renderHealth();
}

async function loadGames() {
  state.games = await apiFetch("/games");
  renderGames();
}

async function loadTargets() {
  state.targets = await apiFetch("/targets");
  renderTargets();
}

async function loadJobs() {
  state.jobs = await apiFetch("/jobs");
  renderJobs();
}

async function refreshAll() {
  try {
    await Promise.all([loadHealth(), loadGames(), loadTargets(), loadJobs()]);
  } catch (error) {
    showToast(error.message, "error");
  }
}

async function triggerScan() {
  try {
    const result = await apiFetch("/scan", { method: "POST" });
    showToast(
      `Scan fertig: ${result.scanned_files} gescannt, +${result.added}, ~${result.updated}, -${result.removed}`
    );
    await loadGames();
  } catch (error) {
    showToast(error.message, "error");
  }
}

async function createTarget(event) {
  event.preventDefault();

  const formData = new FormData(els.targetForm);
  const payload = {
    name: String(formData.get("name") || "").trim(),
    ip_address: String(formData.get("ip_address") || "").trim(),
    ftp_port: Number(formData.get("ftp_port") || 21),
    webman_port: formData.get("webman_port") ? Number(formData.get("webman_port")) : null,
    ftp_username: String(formData.get("ftp_username") || "").trim() || null,
    ftp_password: String(formData.get("ftp_password") || "") || null,
    target_path: String(formData.get("target_path") || "").trim(),
  };

  try {
    await apiFetch("/targets", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    showToast("Target angelegt.");
    els.targetForm.reset();
    els.targetForm.querySelector("input[name='ftp_port']").value = 21;
    els.targetForm.querySelector("input[name='target_path']").value = "/dev_hdd0/PS3ISO";
    await loadTargets();
  } catch (error) {
    showToast(error.message, "error");
  }
}

async function saveCapacity(targetId) {
  const root = document.querySelector(`[data-capacity-target='${targetId}']`);
  if (!root) {
    return;
  }

  const payload = {
    total_bytes: Number(root.querySelector("[data-field='total_bytes']").value || 0),
    reserved_bytes: Number(root.querySelector("[data-field='reserved_bytes']").value || 0),
    used_bytes_estimate: Number(root.querySelector("[data-field='used_bytes_estimate']").value || 0),
  };

  try {
    await apiFetch(`/targets/${targetId}/capacity`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
    showToast(`Kapazität für Target #${targetId} gespeichert.`);
    await loadTargets();
  } catch (error) {
    showToast(error.message, "error");
  }
}

async function createJob(event) {
  event.preventDefault();
  const payload = {
    game_id: Number(els.jobGameId.value),
    target_id: Number(els.jobTargetId.value),
    auto_mount: els.jobAutoMount.checked,
  };

  try {
    const job = await apiFetch("/jobs/cache", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    showToast(`Job #${job.id} wurde erstellt.`);
    await loadJobs();
  } catch (error) {
    showToast(error.message, "error");
  }
}

async function cancelJob(jobId) {
  try {
    await apiFetch(`/jobs/${jobId}/cancel`, { method: "POST" });
    showToast(`Job #${jobId} abgebrochen.`);
    await loadJobs();
  } catch (error) {
    showToast(error.message, "error");
  }
}

document.addEventListener("click", (event) => {
  const gameButton = event.target.closest("[data-select-game]");
  if (gameButton) {
    els.jobGameId.value = gameButton.getAttribute("data-select-game");
    showToast(`Spiel #${els.jobGameId.value} für Job ausgewählt.`);
    return;
  }

  const saveCapacityButton = event.target.closest("[data-save-capacity]");
  if (saveCapacityButton) {
    const targetId = Number(saveCapacityButton.getAttribute("data-save-capacity"));
    void saveCapacity(targetId);
    return;
  }

  const cancelButton = event.target.closest("[data-cancel-job]");
  if (cancelButton) {
    const jobId = Number(cancelButton.getAttribute("data-cancel-job"));
    void cancelJob(jobId);
  }
});

els.scanBtn.addEventListener("click", () => void triggerScan());
els.refreshAllBtn.addEventListener("click", () => void refreshAll());
els.hideAppleDouble.addEventListener("change", renderGames);
els.targetForm.addEventListener("submit", createTarget);
els.jobForm.addEventListener("submit", createJob);

void refreshAll();
setInterval(() => {
  void Promise.all([loadHealth(), loadJobs()]).catch((error) => showToast(error.message, "error"));
}, 5000);
