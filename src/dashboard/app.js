// State Management
let ws = null;
let currentTrackTab = "ALL";
let currentRegion = "ALL";
let soundEnabled = true;
let alerts = [];
let streamItems = [];
let audioCtx = null;

// Synthesized Dual-Harmonic Alert Chime
function playAlertChime() {
  if (!soundEnabled) return;
  try {
    if (!audioCtx) {
      audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    }
    const t = audioCtx.currentTime;
    const osc1 = audioCtx.createOscillator();
    const osc2 = audioCtx.createOscillator();
    const gain = audioCtx.createGain();

    osc1.type = "sine";
    osc1.frequency.setValueAtTime(880, t);
    osc1.frequency.exponentialRampToValueAtTime(1320, t + 0.15);

    osc2.type = "triangle";
    osc2.frequency.setValueAtTime(440, t);
    osc2.frequency.exponentialRampToValueAtTime(880, t + 0.2);

    gain.gain.setValueAtTime(0.25, t);
    gain.gain.exponentialRampToValueAtTime(0.001, t + 0.35);

    osc1.connect(gain);
    osc2.connect(gain);
    gain.connect(audioCtx.destination);

    osc1.start(t);
    osc2.start(t);
    osc1.stop(t + 0.35);
    osc2.stop(t + 0.35);
  } catch (e) {
    console.debug("Audio note:", e);
  }
}

// WebSocket Uplink
function connectWebSocket() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/ws`;

  ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    document.getElementById("beacon-text").textContent = "STREAM ONLINE";
    document.querySelector(".status-beacon").style.color = "var(--color-emerald)";
  };

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      handleWsMessage(data);
    } catch (e) {
      console.error("WS Parse error:", e);
    }
  };

  ws.onclose = () => {
    document.getElementById("beacon-text").textContent = "RECONNECTING...";
    document.querySelector(".status-beacon").style.color = "var(--color-amber)";
    setTimeout(connectWebSocket, 2000);
  };
}

function handleWsMessage(data) {
  if (data.type === "init") {
    alerts = data.alerts || [];
    streamItems = data.recent_events || [];
    renderAlerts();
    renderStream();
    if (data.stats) updateStats(data.stats);
  } else if (data.type === "new_event") {
    streamItems.unshift(data.event);
    if (streamItems.length > 80) streamItems.pop();
    renderStream();
  } else if (data.type === "spike_alert") {
    alerts.unshift(data.alert);
    if (alerts.length > 40) alerts.pop();
    renderAlerts();
    playAlertChime();
  } else if (data.type === "telemetry") {
    updateStats(data.stats);
  }
}

function updateStats(stats) {
  if (!stats) return;
  if (stats.posts_per_second !== undefined) {
    document.getElementById("stat-velocity").innerHTML = `${stats.posts_per_second.toFixed(2)} <span style="font-size: 0.85rem; color: var(--text-muted);">posts/s</span>`;
  }
  if (stats.total_ingested !== undefined) {
    document.getElementById("stat-total").textContent = stats.total_ingested.toLocaleString();
  }
  if (stats.active_alerts !== undefined) {
    document.getElementById("stat-alerts").textContent = stats.active_alerts;
  }
}

function setTrackTab(tab) {
  currentTrackTab = tab;
  document.getElementById("tab-all").classList.toggle("active", tab === "ALL");
  document.getElementById("tab-organic").classList.toggle("active", tab === "organic");
  document.getElementById("tab-inst").classList.toggle("active", tab === "institutional");
  renderStream();
}

function renderStream() {
  const container = document.getElementById("stream-feed");
  const filtered = streamItems.filter(item => {
    if (currentTrackTab !== "ALL" && item.track !== currentTrackTab) return false;
    if (currentRegion !== "ALL" && item.region !== currentRegion && item.region !== "Both") return false;
    return true;
  });

  document.getElementById("stream-count").textContent = `(${filtered.length})`;

  if (filtered.length === 0) {
    container.innerHTML = `<div style="text-align: center; color: var(--text-muted); padding: 3rem 1rem;">No stream events matching current sector filter.</div>`;
    return;
  }

  container.innerHTML = filtered.map(item => {
    const isInst = item.track === "institutional";
    const timeStr = new Date(item.timestamp * 1000).toLocaleTimeString();
    const tokenBadges = (item.matched_tokens || []).map(t => `<span class="feed-pill">${t}</span>`).join(" ");

    return `
      <div class="feed-item ${isInst ? 'institutional' : ''}">
        <div class="feed-header">
          <span><strong>${item.source}</strong> · ${item.region.toUpperCase()}</span>
          <span>${timeStr}</span>
        </div>
        <div class="feed-text">${escapeHtml(item.text)}</div>
        <div class="feed-tokens">${tokenBadges}</div>
      </div>
    `;
  }).join("");
}

function renderAlerts() {
  const container = document.getElementById("alerts-container");
  const filtered = alerts.filter(a => {
    if (currentRegion !== "ALL" && a.region !== currentRegion && a.region !== "Both") return false;
    return true;
  });

  if (filtered.length === 0) {
    container.innerHTML = `
      <div style="text-align: center; color: var(--text-muted); padding: 3rem 1rem;">
        No critical shock spikes currently detected.<br>
        <span style="font-size: 0.8rem; color: var(--color-blue);">Use the Simulation Deck below to test instant event detection.</span>
      </div>`;
    return;
  }

  container.innerHTML = filtered.map(alert => {
    const isInst = alert.track === "institutional";
    const timeAgo = Math.max(1, Math.round(Date.now() / 1000 - alert.timestamp));

    return `
      <div class="alert-card ${isInst ? 'institutional' : ''}">
        <div class="alert-meta">
          <div class="alert-tags">
            <span class="badge-urgency">⚡ URGENCY ${alert.urgency}/10</span>
            <span class="tag-region">📍 ${alert.region.toUpperCase()}</span>
            <span class="tag-zscore">📈 Z: +${alert.z_score}σ</span>
          </div>
          <span style="font-size: 0.75rem; color: var(--text-muted); font-family: var(--font-mono);">${timeAgo}s ago</span>
        </div>

        <div class="alert-headline">${escapeHtml(alert.headline)}</div>
        <div class="alert-summary">${escapeHtml(alert.summary)}</div>

        <div class="alert-footer">
          <span>Sources: <strong>${alert.sources.join(", ")}</strong></span>
          <span class="verifier-tag">🛡️ ${escapeHtml(alert.verified_by)}</span>
        </div>
      </div>
    `;
  }).join("");
}

function escapeHtml(str) {
  if (!str) return "";
  return str.replace(/[&<>"']/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m]));
}

async function triggerSimulation(scenarioKey) {
  try {
    const res = await fetch(`/api/simulate/${scenarioKey}`, { method: "POST" });
    const data = await res.json();
    console.log(`Simulation injected: ${scenarioKey}`, data);
  } catch (e) {
    console.error("Simulation trigger failed:", e);
  }
}

// Event Listeners
document.getElementById("region-filter").addEventListener("change", (e) => {
  currentRegion = e.target.value;
  renderAlerts();
  renderStream();
});

document.getElementById("audio-toggle").addEventListener("click", () => {
  soundEnabled = !soundEnabled;
  const statusSpan = document.getElementById("sound-status");
  const btn = document.getElementById("audio-toggle");
  
  if (soundEnabled) {
    statusSpan.textContent = "ON";
    btn.classList.add("active-sound");
    playAlertChime();
  } else {
    statusSpan.textContent = "MUTED";
    btn.classList.remove("active-sound");
  }
});

// Live UTC Clock
setInterval(() => {
  const now = new Date();
  document.getElementById("live-clock").textContent = now.toUTCString().split(" ")[4] + " UTC";
}, 1000);

// Initialize
connectWebSocket();
