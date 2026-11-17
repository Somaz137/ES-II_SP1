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

const duration = seconds => {
  const total = Math.max(0, Math.round(seconds));
  const h = Math.floor(total / 3600), m = Math.floor(total % 3600 / 60), s = total % 60;
  const parts = [];
  if (h) parts.push(h + " h");
  if (m) parts.push(m + " min");
  if (s || !parts.length) parts.push(s + " s");
  return parts.join(" ");
};
const withUnit = (value, unit) => (format(value) + " " + (unit || "")).trim();
const condition = entry => entry.name + (entry.direction === "low" ? " below " : " above ") +
  withUnit(entry.limit, entry.unit);
const estimateStates = {calibrating: "calibrating, no current value", establishing_baseline:
  "establishing baseline, no current value", unavailable: "no current value"};
// Estimates show a value only when current, always with their word and source label.
function estimateText(block, current) {
  if (!block || !current) return "no current value";
  if (block.state !== "current") return estimateStates[block.state] || "no current value";
  return withUnit(block.value, block.unit) + " · " + (block.band || block.level) + " · " + block.source;
}
function systemLimitText(block) {
  if (!block) return "";
  const limit = block.limit == null ? "no limit set" : "limit " + withUnit(block.limit, block.unit) +
    " for " + duration(block.hold_s);
  return block.name + ": " + limit + " · " + block.check.message;
}

function drawTrend(buckets, now) {
  const points = buckets.map(bucket => [bucket.at, bucket.avg, bucket.min, bucket.max]);
  const svg = byId("trend");
  svg.replaceChildren();
  if (!points.length) {
    byId("trend-summary").textContent = "No readings in the past 24 hours.";
    return;
  }
  const values = points.map(point => point[1]);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const lowest = Math.min(...points.map(point => point[2]));
  const highest = Math.max(...points.map(point => point[3]));
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
    metric.selectedOptions[0].dataset.unit + " · Minute averages · Lowest " + format(lowest) +
    ", highest " + format(highest);
}

const alarmLevels = ["LED and buzzer off", "LED on, buzzer off", "LED and buzzer on"];
const alarmReasons = {not_connected: "serial port not connected", send_failed: "command could not be sent",
  no_confirmation: "the board did not confirm the command"};
function alarmText(alarm) {
  if (!alarm) return "Local alarm state unavailable";
  let text = alarm.state === "unreachable" ?
    "Local alarm unreachable · " + (alarmReasons[alarm.reason] || "unknown reason") +
      " · the host cannot confirm the LED or buzzer · wanted: " + alarmLevels[alarm.wanted_level] :
    alarm.state === "confirmed" ? "Local alarm · " + alarmLevels[alarm.confirmed_level] + " · confirmed by the board" :
    "Local alarm · requesting " + alarmLevels[alarm.wanted_level] + " · waiting for the board";
  if (alarm.silenced) text += " · buzzer silenced at " + new Date(alarm.silenced_at * 1000).toLocaleTimeString();
  return text;
}

let refreshId = 0;
let latest = null;
let refreshSeconds = 10;
async function refresh() {
  const id = ++refreshId;
  try {
    const response = await fetch("/api/room", {cache:"no-store"});
    if (!response.ok) throw new Error("Dashboard data unavailable");
    const data = await response.json();
    const {status, trends, events, now, timing, profile} = data;
    if (id !== refreshId) return;
    latest = data;
    refreshSeconds = timing.dashboard_refresh_s;
    drawTrend(trends[metric.value].buckets, now);
    list("events", events.map(event => new Date(event.at * 1000).toLocaleString() + " · " + event.message));
    const current = status && now - status.updated_at <= timing.status_stale_after_s;
    const since = current ? now - status.updated_at : 0;
    byId("connection").textContent = !status ? "Waiting for first monitor update" :
      !current ? "Monitor update overdue · showing retained readings" :
      "Last monitor update " + new Date(status.updated_at * 1000).toLocaleTimeString();
    byId("occupancy").textContent = "Occupancy · " + label(current ? status.occupancy : "unknown");
    ["temp_c", "humidity_pct", "pressure_hpa", "gas_ohms"].forEach(key => {
      byId(key).textContent = format(status?.last_reading?.[key]);
    });
    byId("dust_mv").textContent = format(status?.dust.sensor_mv);
    byId("air_quality").textContent = estimateText(status?.air_quality, current);
    byId("dust_ugm3").textContent = estimateText(status?.dust_ugm3, current);
    byId("system-limits").textContent = current && status.air_quality ?
      systemLimitText(status.air_quality) + " | " + systemLimitText(status.dust_ugm3) :
      "Air quality and dust limits unavailable";
    byId("profile-label").textContent = profile?.label ? "Profile label · " + profile.label :
      "Profile label not set";
    const lastReading = status?.last_measurement_received_utc_estimate;
    byId("last-reading").textContent = lastReading ?
      "Last BME680 reading " + new Date(lastReading).toLocaleString() : "No BME680 reading received";
    byId("readiness").textContent = !status ? "" : "BME680 · " +
      label(current && status.measurement_current ? status.input_status : "reading unavailable or retained") +
      " | Gas · " + label(current && status.measurement_current ? status.gas_calibration : "unavailable") +
      " | Dust · " + label(current ? status.dust.status : "retained");
    const alerts = current ? status.limit_alerts.map(entry => condition(entry) + " for " +
      duration(entry.elapsed_s + since) + " · now " + withUnit(entry.value, entry.unit)) : [];
    if (current) (status.limit_pending || []).forEach(entry => alerts.push("Pending: " + condition(entry) +
      " for " + duration(entry.elapsed_s + since) + " · alert after " + duration(entry.hold_s) +
      " if it continues · now " + withUnit(entry.value, entry.unit)));
    byId("limit-monitoring").textContent = current && status.limit_monitoring ? status.limit_monitoring.message :
      "Limit monitoring state unavailable";
    if (current && status.communication_alert_active) alerts.push("Communication alert");
    if (current && status.sensor_alert_active) alerts.push("BME680 reading alert");
    if (current && status.profile_error) alerts.push("Patient profile could not be loaded");
    if (current && status.dust.alert_active) alerts.push("Dust reading alert");
    list("alerts", alerts.length ? alerts : [current ? "No active alerts" : "Current alerts unavailable"]);
    byId("ack").hidden = !(current && status.communication_alert_id && !status.communication_timed_out);
    byId("ack").elements.alert_id.value = status?.communication_alert_id || "";
    byId("alarm").textContent = alarmText(current ? status.alarm : null);
    byId("silence").hidden = !(current && status.alarm?.silence_token);
    byId("silence").elements.token.value = status?.alarm?.silence_token || "";
  } catch {
    if (id !== refreshId) return;
    byId("connection").textContent = "Dashboard data unavailable · retrying";
    byId("ack").hidden = true;
    byId("silence").hidden = true;
    byId("alarm").textContent = alarmText(null);
    list("alerts", ["Current alerts unavailable"]);
  }
}
metric.addEventListener("change", () => {
  if (latest) drawTrend(latest.trends[metric.value].buckets, latest.now);
});
async function loop() {
  await refresh();
  setTimeout(loop, refreshSeconds * 1000);
}
loop();
