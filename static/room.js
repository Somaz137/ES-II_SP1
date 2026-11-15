const byId = id => document.getElementById(id);
const metric = byId("metric");
const format = value => value == null ? "—" : Number(value).toLocaleString(undefined, {maximumFractionDigits: 1});
const label = value => (value || "unknown").replaceAll("_", " ");
function list(id, entries) {
  byId(id).replaceChildren(...entries.map(entry => {
    const item = document.createElement("li");
    item.textContent = entry;
    return item;
  }));
}

function drawTrend(points, now) {
  const svg = byId("trend");
  svg.replaceChildren();
  if (!points.length) {
    byId("trend-summary").textContent = "No readings in the past 24 hours.";
    return;
  }
  const values = points.map(point => point[1]);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const ns = "http://www.w3.org/2000/svg";
  let pathData = "";
  let previousTime = null;
  for (const [at, value] of points) {
    const x = 8 + 544 * (at - (now - 86400)) / 86400;
    const y = 184 - 168 * (max === min ? .5 : (value - min) / (max - min));
    pathData += (previousTime === null || at - previousTime > 120 ? " M" : " L") + x + "," + y;
    const dot = document.createElementNS(ns, "circle");
    dot.setAttribute("cx", x);
    dot.setAttribute("cy", y);
    dot.setAttribute("r", 2);
    dot.setAttribute("fill", "#175b48");
    svg.append(dot);
    previousTime = at;
  }
  const line = document.createElementNS(ns, "path");
  line.setAttribute("d", pathData);
  line.setAttribute("fill", "none");
  line.setAttribute("stroke", "#175b48");
  line.setAttribute("stroke-width", "2");
  svg.prepend(line);
  byId("trend-summary").textContent = format(min) + " to " + format(max) + " " +
    metric.selectedOptions[0].dataset.unit + " · Minute averages";
}

let refreshId = 0;
async function refresh() {
  const id = ++refreshId;
  try {
    const response = await fetch("/api/room?metric=" + encodeURIComponent(metric.value), {cache:"no-store"});
    if (!response.ok) throw new Error("Dashboard data unavailable");
    const {status, trend, events, now} = await response.json();
    if (id !== refreshId) return;
    drawTrend(trend, now);
    list("events", events.map(([at, , message]) => new Date(at * 1000).toLocaleString() + " · " + message));
    const current = status && now - status.updated_at <= 15;
    byId("connection").textContent = !status ? "Waiting for first monitor update" :
      !current ? "Monitor update overdue · showing retained readings" :
      "Last monitor update " + new Date(status.updated_at * 1000).toLocaleTimeString();
    byId("occupancy").textContent = "Occupancy · " + label(current ? status.occupancy : "unknown");
    ["temp_c", "humidity_pct", "pressure_hpa", "gas_ohms"].forEach(key => {
      byId(key).textContent = format(status?.last_reading?.[key]);
    });
    byId("dust_mv").textContent = format(status?.dust.sensor_mv);
    const lastReading = status?.last_measurement_received_utc_estimate;
    byId("last-reading").textContent = lastReading ?
      "Last BME680 reading " + new Date(lastReading).toLocaleString() : "No BME680 reading received";
    byId("readiness").textContent = !status ? "" : "BME680 · " +
      label(current && status.measurement_current ? status.input_status : "reading unavailable or retained") +
      " | Gas · " + label(current && status.measurement_current ? status.gas_calibration : "unavailable") +
      " | Dust · " + label(current ? status.dust.status : "retained");
    const alerts = current ? [...status.limit_alerts] : [];
    if (current && status.communication_alert_active) alerts.push("Communication alert");
    if (current && status.sensor_alert_active) alerts.push("BME680 reading alert");
    if (current && status.profile_error) alerts.push("Patient profile could not be loaded");
    if (current && status.dust.alert_active) alerts.push("Dust reading alert");
    list("alerts", alerts.length ? alerts : [current ? "No active alerts" : "Current alerts unavailable"]);
    byId("ack").hidden = !(current && status.communication_alert_id && !status.communication_timed_out);
    byId("ack").elements.alert_id.value = status?.communication_alert_id || "";
  } catch {
    if (id !== refreshId) return;
    byId("connection").textContent = "Dashboard data unavailable · retrying";
    byId("ack").hidden = true;
    list("alerts", ["Current alerts unavailable"]);
  }
}
metric.addEventListener("change", refresh);
refresh();
setInterval(refresh, 10000);
