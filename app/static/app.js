const state = {
  universe: null,
  selectedRoutePlanets: [],
  activePacket: null,
  camera: { x: 0, y: 0, zoom: 1 },
  drag: { active: false, lastX: 0, lastY: 0 },
  ws: null,
};

const canvas = document.getElementById("mapCanvas");
const ctx = canvas.getContext("2d");


// Boot sequence

async function boot() {
  startClock();
  await loadUniverse();
  populateSelects();
  resizeCanvas();
  draw();
  connectWebSocket();
  bindEvents();
}

function startClock() {
  const clockEl = document.getElementById("clock");
  setInterval(() => {
    clockEl.textContent = new Date().toISOString().slice(11, 19) + " UTC";
  }, 1000);
}

async function loadUniverse() {
  const res = await fetch("/api/universe");
  state.universe = await res.json();
}

function populateSelects() {
  const ids = state.universe.planets.map(p => p.id);
  const originSel = document.getElementById("originSelect");
  const destSel = document.getElementById("destSelect");
  const chaosSel = document.getElementById("chaosNodeSelect");

  [originSel, destSel, chaosSel].forEach(sel => sel.innerHTML = "");
  ids.forEach(id => {
    originSel.appendChild(new Option(id, id));
    destSel.appendChild(new Option(id, id));
    chaosSel.appendChild(new Option(id, id));
  });
  if (ids.length > 1) destSel.selectedIndex = 1;
}


// WebSocket (live broadcasts, multi-client safe)

function connectWebSocket() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws`);
  state.ws = ws;

  ws.onopen = () => setConnStatus(true);
  ws.onclose = () => { setConnStatus(false); setTimeout(connectWebSocket, 2000); };
  ws.onerror = () => setConnStatus(false);

  ws.onmessage = (evt) => {
    const msg = JSON.parse(evt.data);
    if (msg.type === "node_killed") onNodeKilled(msg.data.planet_id);
    if (msg.type === "node_revived") onNodeRevived(msg.data.planet_id);
  };
}

function setConnStatus(connected) {
  const pill = document.getElementById("connStatus");
  pill.classList.toggle("connected", connected);
  pill.querySelector("span:last-child").textContent = connected ? "LINK ACTIVE" : "RECONNECTING…";
}

function onNodeKilled(planetId) {
  const p = state.universe.planets.find(pl => pl.id === planetId);
  if (p) p.alive = false;
  draw();
}

function onNodeRevived(planetId) {
  const p = state.universe.planets.find(pl => pl.id === planetId);
  if (p) p.alive = true;
  draw();
}


// Canvas - coordinate mapping

function resizeCanvas() {
  const wrap = canvas.parentElement;
  const dpr = window.devicePixelRatio || 1;
  canvas.width = wrap.clientWidth * dpr;
  canvas.height = wrap.clientHeight * dpr;
  canvas.style.width = wrap.clientWidth + "px";
  canvas.style.height = wrap.clientHeight + "px";
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  fitCameraToUniverse();
}

function fitCameraToUniverse() {
  const planets = state.universe.planets;
  const xs = planets.map(p => p.x);
  const ys = planets.map(p => p.y);
  const minX = Math.min(...xs), maxX = Math.max(...xs);
  const minY = Math.min(...ys), maxY = Math.max(...ys);
  const w = canvas.clientWidth, h = canvas.clientHeight;
  const spanX = Math.max(maxX - minX, 1);
  const spanY = Math.max(maxY - minY, 1);
  const zoom = Math.min((w * 0.7) / spanX, (h * 0.7) / spanY);
  state.camera.zoom = zoom;
  state.camera.x = w / 2 - ((minX + maxX) / 2) * zoom;
  state.camera.y = h / 2 - ((minY + maxY) / 2) * zoom;
}

function worldToScreen(x, y) {
  return {
    x: x * state.camera.zoom + state.camera.x,
    y: y * state.camera.zoom + state.camera.y,
  };
}

function planetScreenRadius(p) {
  return 7 + Math.log2(p.radius_km / 1000 + 1) * 3.2;
}


// Drawing

function draw() {
  const w = canvas.clientWidth, h = canvas.clientHeight;
  ctx.clearRect(0, 0, w, h);

  drawStarfield(w, h);
  drawVoidEdges();
  drawPlanets();
  if (state.activePacket) drawActivePacket();
}

let starfield = null;
function drawStarfield(w, h) {
  if (!starfield || starfield.w !== w || starfield.h !== h) {
    starfield = { w, h, stars: [] };
    for (let i = 0; i < 140; i++) {
      starfield.stars.push({
        x: Math.random() * w, y: Math.random() * h,
        r: Math.random() * 1.1 + 0.2,
        a: Math.random() * 0.5 + 0.15,
      });
    }
  }
  ctx.save();
  starfield.stars.forEach(s => {
    ctx.fillStyle = `rgba(216,220,230,${s.a})`;
    ctx.beginPath();
    ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
    ctx.fill();
  });
  ctx.restore();
}

function planetById(id) {
  return state.universe.planets.find(p => p.id === id);
}

function isEdgeOnActiveRoute(a, b) {
  const path = state.selectedRoutePlanets;
  for (let i = 0; i < path.length - 1; i++) {
    if ((path[i] === a && path[i + 1] === b) || (path[i] === b && path[i + 1] === a)) return true;
  }
  return false;
}

function drawVoidEdges() {
  state.universe.edges.forEach(e => {
    const pa = planetById(e.planet_a);
    const pb = planetById(e.planet_b);
    if (!pa || !pb) return;
    const sa = worldToScreen(pa.x, pa.y);
    const sb = worldToScreen(pb.x, pb.y);

    const onRoute = isEdgeOnActiveRoute(e.planet_a, e.planet_b);

    ctx.save();
    ctx.beginPath();
    ctx.moveTo(sa.x, sa.y);
    ctx.lineTo(sb.x, sb.y);

    if (e.blocked_by_lmax) {
      ctx.strokeStyle = "rgba(255,92,92,0.35)";
      ctx.setLineDash([5, 6]);
      ctx.lineWidth = 1;
    } else if (!e.alive) {
      ctx.strokeStyle = "rgba(255,92,92,0.5)";
      ctx.setLineDash([2, 4]);
      ctx.lineWidth = 1.2;
    } else if (onRoute) {
      ctx.strokeStyle = "#E8C468";
      ctx.shadowColor = "#E8C468";
      ctx.shadowBlur = 10;
      ctx.lineWidth = 2.2;
      ctx.setLineDash([]);
    } else {
      ctx.strokeStyle = "rgba(45,123,130,0.55)";
      ctx.lineWidth = 1;
      ctx.setLineDash([]);
    }
    ctx.stroke();
    ctx.restore();
  });
}

function drawPlanets() {
  state.universe.planets.forEach(p => {
    const s = worldToScreen(p.x, p.y);
    const r = planetScreenRadius(p);
    const onRoute = state.selectedRoutePlanets.includes(p.id);
    const dead = !p.alive;

    const grad = ctx.createRadialGradient(s.x, s.y, r * 0.3, s.x, s.y, r * 2.2);
    if (dead) {
      grad.addColorStop(0, "rgba(255,92,92,0.35)");
      grad.addColorStop(1, "rgba(255,92,92,0)");
    } else if (onRoute) {
      grad.addColorStop(0, "rgba(232,196,104,0.45)");
      grad.addColorStop(1, "rgba(232,196,104,0)");
    } else {
      grad.addColorStop(0, "rgba(79,214,224,0.25)");
      grad.addColorStop(1, "rgba(79,214,224,0)");
    }
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.arc(s.x, s.y, r * 2.2, 0, Math.PI * 2);
    ctx.fill();

    ctx.beginPath();
    ctx.arc(s.x, s.y, r, 0, Math.PI * 2);
    ctx.fillStyle = dead ? "#1a0f0f" : (onRoute ? "#2a2210" : "#0d1520");
    ctx.fill();
    ctx.lineWidth = 1.4;
    ctx.strokeStyle = dead ? "#FF5C5C" : (onRoute ? "#E8C468" : "#3a4a5c");
    ctx.stroke();

    drawTowers(p, s, r, dead, onRoute);

    ctx.font = "600 11px 'Space Grotesk', sans-serif";
    ctx.fillStyle = dead ? "#FF5C5C" : (onRoute ? "#E8C468" : "#D8DCE6");
    ctx.textAlign = "center";
    ctx.fillText(p.id, s.x, s.y - r - 12);

    ctx.font = "10px 'JetBrains Mono', monospace";
    ctx.fillStyle = "#5b6577";
    ctx.fillText(`codex ${p.codex} · ${p.active_towers}T`, s.x, s.y - r - 1);
  });
}

function drawTowers(planet, screenCenter, screenRadius, dead, onRoute) {
  const n = planet.active_towers;
  for (let i = 0; i < n; i++) {
    const angle = (Math.PI / 180) * (360 / n) * i;
    const tx = screenCenter.x + screenRadius * Math.sin(angle);
    const ty = screenCenter.y - screenRadius * Math.cos(angle);
    ctx.beginPath();
    ctx.arc(tx, ty, 1.8, 0, Math.PI * 2);
    ctx.fillStyle = dead ? "#FF5C5C" : (onRoute ? "#E8C468" : "#4FD6E0");
    ctx.fill();
  }
}

function drawActivePacket() {
  const pkt = state.activePacket;
  const fromP = planetById(pkt.path[pkt.fromIdx]);
  const toP = planetById(pkt.path[pkt.fromIdx + 1]);
  if (!fromP || !toP) return;
  const sa = worldToScreen(fromP.x, fromP.y);
  const sb = worldToScreen(toP.x, toP.y);
  const x = sa.x + (sb.x - sa.x) * pkt.progress;
  const y = sa.y + (sb.y - sa.y) * pkt.progress;

  ctx.save();
  ctx.beginPath();
  ctx.arc(x, y, 5, 0, Math.PI * 2);
  ctx.fillStyle = "#4FD6E0";
  ctx.shadowColor = "#4FD6E0";
  ctx.shadowBlur = 18;
  ctx.fill();
  ctx.restore();
}


// Packet animation across the resolved planet_path

function animatePacketAlongPath(planetPath) {
  if (planetPath.length < 2) return;
  state.activePacket = { progress: 0, fromIdx: 0, path: planetPath };
  const DURATION_PER_HOP = 650;
  let hopStart = performance.now();

  function tick(now) {
    const elapsed = now - hopStart;
    const t = Math.min(elapsed / DURATION_PER_HOP, 1);
    state.activePacket.progress = t;
    draw();
    if (t >= 1) {
      if (state.activePacket.fromIdx + 2 < planetPath.length) {
        state.activePacket.fromIdx += 1;
        hopStart = now;
        requestAnimationFrame(tick);
      } else {
        setTimeout(() => { state.activePacket = null; draw(); }, 250);
      }
    } else {
      requestAnimationFrame(tick);
    }
  }
  requestAnimationFrame(tick);
}


// Console - send packet

async function sendPacket() {
  const origin = document.getElementById("originSelect").value;
  const destination = document.getElementById("destSelect").value;
  const message = document.getElementById("messageInput").value || "Hello world";
  const btn = document.getElementById("sendBtn");
  const resultEl = document.getElementById("sendResult");

  if (origin === destination) {
    resultEl.className = "send-result fail";
    resultEl.textContent = "Origin and destination must differ.";
    return;
  }

  btn.disabled = true;
  resultEl.className = "send-result";
  resultEl.textContent = "Transmitting…";

  try {
    const res = await fetch("/api/send", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ origin, destination, message }),
    });
    const data = await res.json();

    if (!data.delivered) {
      resultEl.className = "send-result fail";
      resultEl.textContent = `✕ UNDELIVERABLE — ${data.reason || "no route found"}`;
      state.selectedRoutePlanets = [];
      renderHopLog([], null);
      draw();
      return;
    }

    state.selectedRoutePlanets = data.planet_path;
    resultEl.className = "send-result ok";
    resultEl.textContent =
      `✓ Delivered via ${data.planet_path.join(" → ")} · ${data.total_latency_ms.toFixed(3)} ms total`;

    renderHopLog(data.hop_log, data.breakdown);
    draw();
    animatePacketAlongPath(data.planet_path);
  } catch (err) {
    resultEl.className = "send-result fail";
    resultEl.textContent = "✕ Request failed — backend unreachable.";
  } finally {
    btn.disabled = false;
  }
}


// Hop log + latency breakdown rendering

function renderHopLog(hopLog, breakdown) {
  const tbody = document.getElementById("hopTableBody");
  const subtitle = document.getElementById("logSubtitle");

  if (!hopLog || hopLog.length === 0) {
    tbody.innerHTML = `<tr class="empty-row"><td colspan="8">No deliverable route — see transmission result above.</td></tr>`;
    subtitle.textContent = "transmission failed";
    setBreakdown({ fiber_ms: 0, tower_processing_ms: 0, atmosphere_and_void_ms: 0, total_ms: 0 });
    return;
  }

  subtitle.textContent = `${hopLog.length} log entries · proving the route taken`;
  tbody.innerHTML = hopLog.map((h, i) => `
    <tr class="row-new" style="animation-delay:${i * 40}ms">
      <td>${i + 1}</td>
      <td>${h.planet_id}</td>
      <td>T${h.tower_index}</td>
      <td><span class="event-tag event-${h.event}">${h.event.replace("_", " ")}</span></td>
      <td>base ${h.codex_base}</td>
      <td class="payload-cell">${escapeHtml(h.payload_snapshot)}</td>
      <td>${h.t_p_ms > 0 ? h.t_p_ms.toFixed(3) + " ms" : "—"}</td>
      <td>${h.t_v_ms > 0 ? h.t_v_ms.toFixed(3) + " ms" : "—"}</td>
    </tr>
  `).join("");

  if (breakdown) setBreakdown(breakdown);
}

function setBreakdown(b) {
  const total = b.total_ms || 0.0001;
  document.querySelector(".seg-fiber").style.width = (b.fiber_ms / total * 100).toFixed(2) + "%";
  document.querySelector(".seg-tower").style.width = (b.tower_processing_ms / total * 100).toFixed(2) + "%";
  document.querySelector(".seg-void").style.width = (b.atmosphere_and_void_ms / total * 100).toFixed(2) + "%";

  const list = document.getElementById("breakdownList");
  list.children[0].querySelector("strong").textContent = b.fiber_ms.toFixed(3) + " ms";
  list.children[1].querySelector("strong").textContent = b.tower_processing_ms.toFixed(3) + " ms";
  list.children[2].querySelector("strong").textContent = b.atmosphere_and_void_ms.toFixed(3) + " ms";

  document.getElementById("totalLatencyValue").textContent = b.total_ms.toFixed(3) + " ms";
}

function escapeHtml(str) {
  return String(str).replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}


// Console - chaos test

async function killNode() {
  const planetId = document.getElementById("chaosNodeSelect").value;
  await fetch("/api/chaos/kill-node", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ planet_id: planetId }),
  });
  onNodeKilled(planetId);
  logChaos(`✕ ${planetId} OFFLINE — towers dark, routes will reroute around it`, "kill");
}

async function reviveNode() {
  const planetId = document.getElementById("chaosNodeSelect").value;
  await fetch("/api/chaos/revive-node", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ planet_id: planetId }),
  });
  onNodeRevived(planetId);
  logChaos(`✓ ${planetId} back online`, "revive");
}

function logChaos(text, kind) {
  const log = document.getElementById("chaosLog");
  const line = document.createElement("div");
  line.className = kind === "kill" ? "entry-kill" : "entry-revive";
  const ts = new Date().toISOString().slice(11, 19);
  line.textContent = `[${ts}] ${text}`;
  log.prepend(line);
}


// Canvas interaction - pan, zoom, click-to-target

function bindEvents() {
  document.getElementById("sendBtn").addEventListener("click", sendPacket);
  document.getElementById("killBtn").addEventListener("click", killNode);
  document.getElementById("reviveBtn").addEventListener("click", reviveNode);
  document.getElementById("messageInput").addEventListener("keydown", e => {
    if (e.key === "Enter") sendPacket();
  });

  window.addEventListener("resize", () => { resizeCanvas(); draw(); });

  canvas.addEventListener("mousedown", e => {
    state.drag.active = true;
    state.drag.lastX = e.clientX;
    state.drag.lastY = e.clientY;
  });
  window.addEventListener("mouseup", () => { state.drag.active = false; });
  window.addEventListener("mousemove", e => {
    if (!state.drag.active) return;
    state.camera.x += e.clientX - state.drag.lastX;
    state.camera.y += e.clientY - state.drag.lastY;
    state.drag.lastX = e.clientX;
    state.drag.lastY = e.clientY;
    draw();
  });

  canvas.addEventListener("wheel", e => {
    e.preventDefault();
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left, my = e.clientY - rect.top;
    const worldX = (mx - state.camera.x) / state.camera.zoom;
    const worldY = (my - state.camera.y) / state.camera.zoom;
    const factor = e.deltaY < 0 ? 1.1 : 0.9;
    state.camera.zoom *= factor;
    state.camera.x = mx - worldX * state.camera.zoom;
    state.camera.y = my - worldY * state.camera.zoom;
    draw();
  }, { passive: false });

  canvas.addEventListener("click", e => {
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left, my = e.clientY - rect.top;
    const hit = hitTestPlanet(mx, my);
    if (hit) {
      document.getElementById("destSelect").value = hit.id;
      flashPlanetTarget(hit.id);
    }
  });
}

function hitTestPlanet(mx, my) {
  for (const p of state.universe.planets) {
    const s = worldToScreen(p.x, p.y);
    const r = planetScreenRadius(p) + 4;
    const dx = mx - s.x, dy = my - s.y;
    if (dx * dx + dy * dy <= r * r) return p;
  }
  return null;
}

function flashPlanetTarget(planetId) {
  const resultEl = document.getElementById("sendResult");
  resultEl.className = "send-result";
  resultEl.textContent = `Destination set to ${planetId}.`;
}

boot();
