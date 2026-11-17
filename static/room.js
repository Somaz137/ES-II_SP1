// Room dashboard: polls /api/room and fills the shared frame and the current page.
"use strict";
const $ = id => document.getElementById(id);
const PAGE = document.body.dataset.page;
const PATIENT = ["temp_c", "humidity_pct", "pressure_hpa"];
const SYSTEM = ["air_quality", "dust_ugm3"];
const SHOWN = [...PATIENT, ...SYSTEM];
const SHORT = {temp_c: "Temperature", humidity_pct: "Humidity", pressure_hpa: "Pressure",
  air_quality: "Air quality", dust_ugm3: "Dust"};
const UNIT = {temp_c: "°C", humidity_pct: "%", pressure_hpa: "hPa", air_quality: "", dust_ugm3: "µg/m³"};
const DIGITS = {temp_c: 1, humidity_pct: 0, pressure_hpa: 0, air_quality: 0, dust_ugm3: 0};
const WINDOWS = {"24h": {span: 86400, bucket: 60, words: "last 24 hours", note: "Minute averages"},
  "7d": {span: 7 * 86400, bucket: 600, words: "last 7 days", note: "10-minute averages"}};

// ---------- wording helpers ----------
const fmt = (value, key) => value == null ? "—" : Number(value).toFixed(DIGITS[key] ?? 1);
const withUnit = (value, key) => (fmt(value, key) + " " + (UNIT[key] || "")).trim();
function duration(seconds) {
  const total = Math.max(0, Math.round(seconds));
  const d = Math.floor(total / 86400), h = Math.floor(total % 86400 / 3600), m = Math.floor(total % 3600 / 60), s = total % 60;
  if (d) return d + " d" + (h ? " " + h + " h" : "");
  if (h) return h + " h" + (m ? " " + m + " min" : "");
  if (m) return m + " min";
  return s + " s";
}
const alertIn = seconds => seconds < 1 ? "alert due now" : "alert in " + duration(seconds);
const ago = seconds => seconds == null ? "age unknown" : duration(seconds) + " ago";
const clock = at => RoomChart.clock(at);
function dayWords(at, now) {
  const date = new Date(at * 1000), today = new Date(now * 1000);
  const start = d => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const diff = Math.round((start(today) - start(date)) / 86400e3);
  const long = date.toLocaleDateString("en-GB", {day: "numeric", month: "long"});
  return diff === 0 ? "Today, " + long : diff === 1 ? "Yesterday, " + long :
    date.toLocaleDateString("en-GB", {weekday: "long"}) + ", " + long;
}
function setTone(node, tone, words) {
  if (!node) return;
  node.dataset.tone = tone;
  if (words !== undefined) node.textContent = words;
}
const word = value => (value || "unknown").replaceAll("_", " ");

// ---------- the derived view of one API response ----------
function derive(data) {
  const {status, now, timing, profile} = data;
  const current = !!status && now - status.updated_at <= timing.status_stale_after_s;
  const since = status ? Math.max(0, now - status.updated_at) : 0;
  const limits = {};
  for (const key of PATIENT) {
    const pair = profile?.limits?.[key];
    limits[key] = pair ? {low: pair[0], high: pair[1]} : null;
  }
  for (const key of SYSTEM) {
    const limit = status?.[key]?.limit;
    limits[key] = limit == null ? null : {low: null, high: limit, hold: status[key].hold_s};
  }
  const alerts = {}, pending = {};
  if (current) {
    for (const entry of status.limit_alerts || []) alerts[entry.metric] = entry;
    for (const entry of status.limit_pending || []) pending[entry.metric] = entry;
  }
  return {...data, current, since, limits, alerts, pending};
}

// One measurement in words: the value, whether it is fresh, its state chip and its age.
function reading(v, key) {
  const {status, current, since, limits} = v;
  const limit = limits[key];
  const out = {key, value: null, fresh: "none", chip: "No reading", tone: "none", age: null, meta: ""};
  if (PATIENT.includes(key)) {
    const value = status?.last_reading?.[key];
    if (value == null) return out;
    out.value = value;
    out.age = status.measurement_age_s == null ? null : status.measurement_age_s + since;
    if (!(current && status.measurement_current)) {
      out.fresh = "retained";
      out.chip = "Retained reading";
      return out;
    }
    out.fresh = "fresh";
  } else {
    const block = status?.[key];
    out.age = key === "dust_ugm3" ? (status?.dust?.age_s == null ? null : status.dust.age_s + since) :
      (status?.measurement_age_s == null ? null : status.measurement_age_s + since);
    const source = key === "air_quality" ? "Bosch estimate" : "estimate";
    if (!block || !current) { out.chip = "No current value"; return out; }
    if (block.state !== "current") {
      out.fresh = "word";
      out.word = {calibrating: "Calibrating", establishing_baseline: "Establishing baseline"}[block.state] || "No current value";
      out.chip = out.word + " · " + source;
      return out;
    }
    out.value = block.value;
    out.fresh = "fresh";
    const band = block.band || block.level || "";
    out.band = band.charAt(0).toUpperCase() + band.slice(1);
    out.source = source;
  }
  const alert = v.alerts[key], wait = v.pending[key];
  const side = entry => entry.direction === "low" ? "Below limit" : "Above limit";
  if (alert) { out.tone = "red"; out.chip = side(alert) + " · " + duration(alert.elapsed_s + since); }
  else if (wait) {
    out.tone = "amber";
    out.chip = side(wait) + " · " + alertIn(wait.hold_s - wait.elapsed_s - since);
  } else if (limit) {
    const off = RoomChart.outside(out.value, limit.low, limit.high);
    out.tone = off ? "amber" : "green";
    out.chip = off ? "Outside limits" : "Within limits";
  } else { out.tone = "none"; out.chip = "No limit set"; }
  if (out.band) out.chip = (alert || wait ? out.chip + " · " : out.band + " · ") + out.source;
  return out;
}

function limitText(v, key) {
  const limit = v.limits[key];
  if (PATIENT.includes(key)) return limit ? `Range ${fmt(limit.low, key)}–${fmt(limit.high, key)} ${UNIT[key]}` : "No range configured";
  if (!v.status?.[key]) return "System limit not known";
  return limit ? `System limit ${withUnit(limit.high, key)} for ${duration(limit.hold)}` : "No system limit configured";
}

// ---------- top bar ----------
const ALARM_LEVEL = ["LED and buzzer off", "LED on, buzzer off", "LED and buzzer on"];
function alarmState(v) {
  const alarm = v.current ? v.status.alarm : null;
  if (!alarm) return {tone: "none", text: "Alarm state unknown", chip: "Unknown"};
  if (alarm.state === "unreachable") return {tone: "red", text: "Alarm unreachable", chip: "Unreachable"};
  if (alarm.state !== "confirmed") return {tone: "amber", text: "Alarm: waiting for the board", chip: "Waiting for the board"};
  const level = alarm.confirmed_level;
  if (level === 2 && !alarm.silenced) return {tone: "red", text: "Alarm: LED and buzzer on", chip: "Sounding"};
  if (alarm.silenced) return {tone: "amber", text: "Alarm: buzzer silenced, LED on", chip: "Buzzer silenced"};
  if (level === 1) return {tone: "amber", text: "Alarm: LED on, buzzer off", chip: "LED on"};
  return {tone: "green", text: "Alarm off", chip: "Off"};
}
function renderTop(v) {
  const {status, current, since, profile} = v;
  $("profile-label").textContent = "Room 01" + (profile?.label ? " · " + profile.label : "");
  if (!status) { setTone($("connection-dot"), "none"); $("connection").textContent = "Waiting for monitor"; }
  else if (current) { setTone($("connection-dot"), "green"); $("connection").textContent = "Monitor live · " + ago(since); }
  else { setTone($("connection-dot"), "red"); $("connection").textContent = "Monitor overdue · last update " + ago(since); }
  const occ = current ? status.occupancy : "unknown";
  const age = status?.occupancy_observation_age_s;
  const how = !current ? "" : age != null ? " · checked " + ago(age + since) :
    status.occupancy_source === "simulated" ? " · simulated" : status.occupancy_source === "none" ? " · no camera" : "";
  $("occupancy").textContent = (occ === "occupied" ? "Occupied" : occ === "unknown" ? "Occupancy unknown" : "Not occupied") + how;
  setTone($("occupancy-dot"), occ === "occupied" ? "green" : occ === "unknown" ? "amber" : "none");
  const alarm = alarmState(v);
  setTone($("alarm-dot"), alarm.tone);
  $("alarm").textContent = alarm.text;
}

// ---------- attention panel ----------
const condition = (e, key) => `${SHORT[key] || e.name} ${e.direction === "low" ? "below" : "above"} ${withUnit(e.limit, key)}`;
function restoredAt(events) {
  const found = (events || []).find(e => e.kind === "fault_ended" && e.message.startsWith("Communication"));
  return found ? " · contact restored " + clock(found.at) : " · contact restored";
}
let lastAnnounced = null;
function renderAttention(v, failed) {
  const rows = {alert: $("att-alert"), ack: $("att-ack"), pending: $("att-pending"), calm: $("att-calm")};
  const compact = !document.getElementById("attention").classList.contains("att-full");
  const {status, current, since} = v || {};
  const red = [], redKeys = [];
  let sub = "";
  if (current) {
    for (const e of status.limit_alerts || []) {
      red.push(`${condition(e, e.metric)} for ${duration(e.elapsed_s + since)} · now ${withUnit(e.value, e.metric)}`);
      redKeys.push(e.metric + e.direction);
    }
    const first = (status.limit_alerts || [])[0];
    if (first) {
      const alarm = alarmState(v);
      sub = "Outside the configured limit since " + clock(first.breach_started_at ?? (v.now - first.elapsed_s - since)) +
        (alarm.chip === "Sounding" ? " · local buzzer sounding in the room" : alarm.chip === "Buzzer silenced" ? " · buzzer silenced, LED on" : "");
    }
    if (status.communication_alert_active && status.communication_timed_out) {
      red.push("Communication alert · no contact with the ESP32 for " + duration((status.last_contact_age_s ?? 0) + since));
      redKeys.push("comm");
    }
    if (status.sensor_alert_active) { red.push("Sensor alert · BME680 readings are not arriving"); redKeys.push("bme"); }
    if (status.dust?.alert_active) { red.push("Sensor alert · dust readings are not arriving"); redKeys.push("dust"); }
    if (status.profile_error) { red.push("The patient limits could not be loaded"); redKeys.push("profile"); }
    if (status.alarm?.state === "unreachable") { red.push("Local alarm unreachable · the LED and buzzer cannot be confirmed"); redKeys.push("alarm"); }
  }
  rows.alert.hidden = !red.length;
  $("att-alert-text").textContent = compact && red.length > 1 ? red[0] + " · and " + (red.length - 1) + " more" : red[0] || "";
  $("att-alert-sub").textContent = [compact ? "" : red.slice(1).join(" · "), sub].filter(Boolean).join(" · ");
  const token = current ? status.alarm?.silence_token : null;
  $("silence").hidden = !token;
  $("silence").elements.token.value = token || "";

  const ack = current && status.communication_alert_id && status.communication_timed_out === false;
  rows.ack.hidden = !ack;
  $("ack").hidden = !ack;
  $("ack").elements.alert_id.value = ack ? status.communication_alert_id : "";
  $("att-ack-text").textContent = ack ? "Communication alert" + restoredAt(v.events) : "";

  const waits = current ? status.limit_pending || [] : [];
  rows.pending.hidden = !waits.length;
  const waitText = e => `${condition(e, e.metric)} for ${duration(e.elapsed_s + since)} · ` +
    `${alertIn(e.hold_s - e.elapsed_s - since)} if it continues · now ${withUnit(e.value, e.metric)}`;
  $("att-pending-text").textContent = waits.length ? waitText(waits[0]) + (compact && waits.length > 1 ? " · and " + (waits.length - 1) + " more" : "") : "";
  $("att-pending-sub").textContent = compact ? "" : waits.slice(1).map(waitText).join(" · ");

  const calm = rows.calm;
  const nothing = !red.length && !ack && !waits.length;
  calm.hidden = !nothing;
  let lab = "No action needed", text = "No limit, communication or sensor alert is active.", tone = "calm";
  if (failed) { lab = "Data unavailable"; text = "The dashboard cannot reach its data. Retrying."; tone = "amber"; }
  else if (!status) { lab = "Waiting"; text = "Waiting for the first monitor update."; tone = "calm"; }
  else if (!current) { lab = "Monitor overdue"; text = "No monitor update for " + duration(since) + ". Alerts cannot be confirmed and the readings shown are retained."; tone = "amber"; }
  else if (status.limit_monitoring?.state && status.limit_monitoring.state !== "running") text += " " + status.limit_monitoring.message;
  calm.dataset.tone = tone;
  $("att-calm-lab").textContent = lab;
  $("att-calm-text").textContent = text;

  // Announce only changes in what needs attention, never each refresh.
  const key = failed ? "failed" : !current ? "stale" : [redKeys.join(), ack ? "ack" : "", waits.map(e => e.metric).join()].join("|");
  if (lastAnnounced !== null && key !== lastAnnounced) {
    $("att-live").textContent = red.length ? "Alerting: " + red.map(t => t.split(" for ")[0]).join("; ") + "." :
      ack ? "Communication alert to acknowledge." : waits.length ? "Limit breach pending." : lab + ". " + text;
  }
  lastAnnounced = key;
}

// ---------- overview ----------
function placeRange(box, v, key, r, trend) {
  const limit = v.limits[key];
  const values = (trend?.buckets || []).flatMap(b => [b.min, b.max]);
  if (r.value != null) values.push(r.value);
  let lo, hi;
  if (limit && limit.low != null) {
    const span = limit.high - limit.low;
    lo = limit.low - span * .6; hi = limit.high + span * .6;
  } else if (limit) { lo = 0; hi = limit.high * 2; }
  else if (values.length) {
    lo = Math.min(...values); hi = Math.max(...values);
    const pad = (hi - lo) * .2 || Math.abs(hi) * .02 || 1;
    lo -= pad; hi += pad;
  } else { lo = 0; hi = 1; }
  if (r.value != null && r.fresh !== "word" && (r.value < lo || r.value > hi)) {
    // Keep the dot inside the bar with a little room at the end.
    const span = Math.max(hi, r.value) - Math.min(lo, r.value);
    lo = Math.min(lo, r.value - span * .05); hi = Math.max(hi, r.value + span * .05);
  }
  const pct = value => (100 * (value - lo) / (hi - lo || 1)).toFixed(2) + "%";
  const track = document.createElement("div");
  track.className = "range-track";
  const parts = [track];
  const tick = (value, edge) => {
    const node = document.createElement("span");
    node.className = "range-tick";
    node.style.left = edge === "end" ? "100%" : edge === "start" ? "0" : pct(value);
    if (edge) node.dataset.edge = edge;
    node.textContent = fmt(value, key);
    parts.push(node);
  };
  if (limit) {
    track.dataset.banded = "";
    const band = document.createElement("div");
    band.className = "range-band";
    band.style.left = limit.low == null ? "0" : pct(limit.low);
    band.style.right = (100 - parseFloat(pct(limit.high))).toFixed(2) + "%";
    track.append(band);
    if (limit.low == null) tick(0, "start"); else tick(limit.low);
    tick(limit.high);
  } else if (values.length) { tick(lo, "start"); tick(hi, "end"); }
  if (r.value != null && r.fresh !== "word" && r.fresh !== "none") {
    const dot = document.createElement("span");
    dot.className = "range-dot";
    dot.dataset.tone = r.fresh === "retained" ? "none" : r.tone === "none" ? "none" : r.tone;
    dot.style.left = pct(r.value);
    parts.push(dot);
  }
  box.replaceChildren(...parts);
}

function renderTiles(v) {
  for (const key of SHOWN) {
    const r = reading(v, key);
    const val = $(key).parentElement;
    val.dataset.fresh = r.fresh;
    $(key).textContent = r.fresh === "word" ? r.word : r.fresh === "none" && r.value == null ? "—" : fmt(r.value, key);
    setTone($(key + "-chip"), r.fresh === "fresh" ? r.tone : "none", r.chip);
    placeRange($(key + "-range"), v, key, r, v.trends[key]);
    const age = r.fresh === "retained" ? "last reading " + ago(r.age) + ", not current" :
      r.fresh === "none" ? (v.status ? "no current value" : "waiting for the first reading") : ago(r.age);
    $(key + "-meta").textContent = limitText(v, key) + " · " + age;
  }
}

function summarise(buckets, key, limit, bucketS) {
  if (!buckets.length) return null;
  const lows = buckets.map(b => b.min), highs = buckets.map(b => b.max);
  const out = buckets.filter(b => limit && RoomChart.outside(b.avg, limit.low, limit.high)).length;
  return {low: Math.min(...lows), high: Math.max(...highs),
    avg: buckets.reduce((sum, b) => sum + b.avg, 0) / buckets.length, outsideS: out * bucketS};
}

let overviewMetric = "temp_c";
function renderOverviewChart(v) {
  const key = overviewMetric, trend = v.trends[key], limit = v.limits[key];
  const buckets = trend.buckets, w = WINDOWS["24h"];
  const alert = v.alerts[key];
  const sum = summarise(buckets, key, limit, w.bucket);
  const summary = !sum ? `${SHORT[key]}: no readings in the last 24 hours.` :
    `${SHORT[key]}, last 24 hours, minute averages: lowest ${withUnit(sum.low, key)}, average ${withUnit(sum.avg, key)}, highest ${withUnit(sum.high, key)}.` +
    (limit ? ` Outside the configured limits for ${duration(sum.outsideS)}.` : " No limit set.") +
    (trend.estimate ? " Estimate." : "");
  RoomChart.draw($("overview-chart"), {buckets, start: v.now - w.span, end: v.now, bucketS: w.bucket,
    low: limit?.low ?? null, high: limit?.high ?? null, digits: DIGITS[key], unit: UNIT[key], name: SHORT[key], summary,
    alertLabel: alert ? (alert.direction === "low" ? "below" : "above") + " limit · " + duration(alert.elapsed_s + v.since) : null});
  $("overview-chart-summary").textContent = summary;
}

const FAMILY = {limit: "Limit alert", communication: "Communication", sensor: "Sensor", alarm: "Alarm", profile: "Profile"};
const FAMILY_TONE = {limit: "red", communication: "amber", sensor: "none", alarm: "red", profile: "none"};
function family(event) {
  if (event.kind.startsWith("limit")) return "limit";
  if (event.kind.startsWith("alarm")) return "alarm";
  if (event.kind.startsWith("profile")) return "profile";
  if (event.kind.startsWith("communication")) return "communication";
  return event.message.startsWith("Communication") ? "communication" : "sensor";
}
function renderRecent(v) {
  const list = $("recent-events");
  const items = v.events.slice(0, 4).map(event => {
    const li = document.createElement("li");
    const time = document.createElement("time");
    time.dateTime = new Date(event.at * 1000).toISOString();
    time.textContent = clock(event.at);
    const b = document.createElement("b");
    b.textContent = FAMILY[family(event)];
    const msg = document.createElement("span");
    msg.className = "ev-msg";
    msg.textContent = event.message;
    li.append(time, b, msg);
    return li;
  });
  if (!items.length) {
    const li = document.createElement("li");
    li.className = "ev-empty";
    li.textContent = "No events yet.";
    items.push(li);
  }
  list.replaceChildren(...items);
}

// ---------- trends ----------
// The window can be linked to as /trends?window=7d.
let trendWindow = new URLSearchParams(location.search).get("window") === "7d" ? "7d" : "24h";
function renderTrends(v) {
  const w = WINDOWS[trendWindow];
  const start = v.now - w.span;
  $("trend-note").textContent = w.note + " · lowest and highest are in the table";
  $("summary-title").textContent = "Summary, " + w.words;
  const rows = [];
  for (const key of SHOWN) {
    const trend = v.trends[key], limit = v.limits[key], r = reading(v, key);
    const sum = summarise(trend.buckets, key, limit, w.bucket);
    $(key + "-trend-unit").textContent = (key === "air_quality" ? "index" : UNIT[key]) + " · " +
      (limit ? (limit.low != null ? `range ${fmt(limit.low, key)}–${fmt(limit.high, key)}` : "limit " + fmt(limit.high, key)) : "no limit set") +
      (trend.estimate ? " · estimate" : "");
    const now = $(key + "-trend-now"), state = $(key + "-trend-state");
    now.textContent = r.fresh === "word" ? "" : r.value == null ? "—" : fmt(r.value, key);
    state.textContent = r.fresh === "word" ? r.word : r.fresh === "retained" ? "retained, " + ago(r.age) :
      r.fresh === "none" ? "no current value" : r.band || r.chip;
    if (r.fresh === "fresh" && !r.band) state.textContent = r.chip;
    now.parentElement.dataset.tone = r.fresh === "fresh" ? r.tone : "none";
    now.parentElement.dataset.fresh = r.fresh;
    const alert = v.alerts[key];
    const label = sum && sum.outsideS ? (alert ? (alert.direction === "low" ? "below" : "above") + " limit now · " : "outside limits · ") +
      duration(sum.outsideS) + " in total" : null;
    RoomChart.draw($(key + "-trend"), {buckets: trend.buckets, start, end: v.now, bucketS: w.bucket, small: true,
      low: limit?.low ?? null, high: limit?.high ?? null, digits: DIGITS[key], unit: UNIT[key], name: SHORT[key],
      alertLabel: label, noteLabel: limit ? null : "no limit set",
      summary: `${SHORT[key]}, ${w.words}. ` + (sum ? `Lowest ${withUnit(sum.low, key)}, highest ${withUnit(sum.high, key)}.` : "No readings.")});
    const tr = document.createElement("tr");
    const cell = (content, cls) => { const td = document.createElement("td"); td.textContent = content; if (cls) td.className = cls; tr.append(td); };
    const th = document.createElement("th");
    th.scope = "row";
    th.textContent = `${SHORT[key]} (${key === "air_quality" ? "index" : UNIT[key]})` + (trend.estimate ? ", estimate" : "");
    tr.append(th);
    if (!sum) { cell("no readings", "num muted"); cell("—", "num"); cell("—", "num"); }
    else {
      cell(fmt(sum.low, key), "num" + (limit && limit.low != null && sum.low < limit.low ? " alert-text" : ""));
      cell(fmt(sum.avg, key), "num");
      cell(fmt(sum.high, key), "num" + (limit && sum.high > limit.high ? " alert-text" : ""));
    }
    cell(!limit ? "no limit set" : !sum ? "—" : sum.outsideS ? duration(sum.outsideS) : "none",
      !limit ? "muted" : sum && sum.outsideS ? "alert-text" : "");
    rows.push(tr);
  }
  $("summary-body").replaceChildren(...rows);
  const axis = $("trend-axis");
  axis.replaceChildren(...RoomChart.timeTicks(start, v.now).map(t => {
    const span = document.createElement("span");
    const p = 100 * (t.at - start) / w.span;
    span.style.left = p + "%";
    if (p < 3) span.dataset.edge = "start"; else if (p > 97) span.dataset.edge = "end";
    span.textContent = t.label;
    return span;
  }));
}

// ---------- events ----------
let eventList = [], eventsMore = false, eventFilter = "all", loadingOlder = false;
function mergeEvents(fresh) {
  const seen = new Set(eventList.map(e => e.id));
  eventList = [...fresh.filter(e => !seen.has(e.id)), ...eventList].sort((a, b) => b.id - a.id);
}
function eventState(v, event, index) {
  const newer = eventList.slice(0, index);
  const fam = family(event);
  const subject = event.message.split(/ (above|below) /)[0];
  if (event.kind === "limit_alert") {
    const active = v.current && (v.status.limit_alerts || []).find(a => (a.name === subject || SHORT[a.metric] === subject));
    const newest = !newer.some(e => e.kind === "limit_alert" && e.message.startsWith(subject + " "));
    if (active && newest) return {tone: "red", text: "Active · " + duration(active.elapsed_s + v.since)};
    return {text: "Ended"};
  }
  if (event.kind.startsWith("limit_")) return {text: "Resolved"};
  if (event.kind === "fault" || event.kind === "fault_ended") {
    const name = event.message.split(" alert")[0];
    const newest = !newer.some(e => (e.kind === "fault" || e.kind === "fault_ended") && e.message.startsWith(name + " alert"));
    if (event.kind === "fault") {
      const active = v.current && newest && ((name === "Communication" && v.status.communication_alert_active) ||
        (name === "BME680" && v.status.sensor_alert_active) || (name !== "Communication" && name !== "BME680" && v.status.dust?.alert_active));
      return active ? {tone: "red", text: "Active"} : {text: "Ended"};
    }
    if (fam === "communication" && newest && v.current && v.status.communication_alert_id && v.status.communication_timed_out === false)
      return {tone: "amber", text: "To acknowledge", ack: true};
    return {text: "Resolved"};
  }
  if (fam === "alarm") {
    const newest = !newer.some(e => family(e) === "alarm");
    return newest && v.current ? (s => ({tone: s.tone === "green" ? "" : s.tone, text: s.chip}))(alarmState(v)) : {text: "Recorded"};
  }
  if (fam === "profile") return {text: newer.some(e => e.kind === "profile_changed") ? "Replaced" : "In force"};
  if (event.kind === "communication_acknowledged") return {text: "Done"};
  return {text: "Recorded"};
}
function renderEvents(v) {
  const body = $("event-body");
  const rows = [];
  let day = null, shown = 0;
  eventList.forEach((event, index) => {
    const fam = family(event);
    if (eventFilter !== "all" && fam !== eventFilter) return;
    shown++;
    const label = dayWords(event.at, v.now);
    if (label !== day) {
      day = label;
      const tr = document.createElement("tr");
      const td = document.createElement("th");
      td.colSpan = 4; td.className = "day"; td.scope = "colgroup";
      td.textContent = label;
      tr.append(td); rows.push(tr);
    }
    const tr = document.createElement("tr");
    const td = cls => { const c = document.createElement("td"); if (cls) c.className = cls; tr.append(c); return c; };
    const t = td("t");
    t.textContent = clock(event.at);
    const chip = document.createElement("span");
    chip.className = "chip";
    // Alarm events are red only when the alarm sounded or could not be confirmed.
    const tone = fam === "alarm" && !/level 2|unreachable/.test(event.message) ? "none" : FAMILY_TONE[fam];
    setTone(chip, tone, FAMILY[fam]);
    td("ty").append(chip);
    td().textContent = event.message;
    const state = eventState(v, event, index);
    const s = td("s");
    const wrap = document.createElement("div");
    wrap.className = "state-cell";
    const words = document.createElement("span");
    words.textContent = state.text;
    words.className = state.tone === "red" ? "state-red" : state.tone === "amber" ? "state-amber" : "muted";
    wrap.append(words);
    if (state.ack) {
      const button = document.createElement("button");
      button.className = "btn btn-sm btn-amber";
      button.setAttribute("form", "ack");
      button.dataset.control = "";
      button.textContent = "Acknowledge";
      wrap.append(button);
    }
    s.append(wrap);
    rows.push(tr);
  });
  if (!rows.length) {
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = 4; td.className = "muted";
    td.textContent = eventList.length ? "No events of this type in the loaded events." : "No events recorded yet.";
    tr.append(td); rows.push(tr);
  }
  body.replaceChildren(...rows);
  $("event-count").textContent = shown + (shown === 1 ? " event" : " events") + " shown" + (eventsMore ? ", older events available" : "");
  $("older").hidden = !eventsMore;
}

// ---------- patient limits ----------
function renderLimits(v) {
  for (const key of PATIENT) {
    const r = reading(v, key);
    $(key + "-now").textContent = r.value == null ? "—" : fmt(r.value, key);
    $(key + "-now").classList.toggle("muted", r.fresh !== "fresh");
    setTone($(key + "-now-chip"), r.fresh === "fresh" ? r.tone : "none",
      (r.fresh === "fresh" ? r.chip : r.fresh === "retained" ? "retained, " + ago(r.age) : "no reading").toLowerCase());
  }
  for (const key of SYSTEM) {
    const block = v.status?.[key];
    $(key + "-system-limit").textContent = !block ? "not known until the monitor reports" :
      block.limit == null ? "off, no limit configured" :
      `alert above ${withUnit(block.limit, key)} for ${duration(block.hold_s)}` + (block.check?.message ? ". " + block.check.message : "");
  }
}
function wireLimitsForm() {
  const form = $("profile-form");
  if (!form) return;
  for (const node of document.querySelectorAll("time[data-at]")) {
    const at = Number(node.dataset.at);
    node.textContent = dayWords(at, Date.now() / 1000).split(",")[0].toLowerCase() + " " + clock(at);
  }
  const show = (id, messages, inputs) => {
    const box = $(id);
    box.textContent = messages.join(" ");
    box.hidden = !messages.length;
    for (const input of inputs) {
      if (messages.length) { input.setAttribute("aria-invalid", "true"); input.setAttribute("aria-describedby", id); }
      else input.removeAttribute("aria-invalid");
    }
  };
  const number = text => text.trim() !== "" && isFinite(Number(text.trim()));
  form.addEventListener("submit", event => {
    let firstBad = null;
    for (const key of PATIENT) {
      const low = form.elements[key + "_low"], high = form.elements[key + "_high"];
      const name = SHORT[key], messages = [];
      const a = low.value.trim(), b = high.value.trim();
      if (a || b) {
        if (!a || !b) messages.push(`Enter both ${name} limits, or leave both blank.`);
        else {
          if (!number(a)) messages.push(`${name} lower limit must be a finite number.`);
          if (!number(b)) messages.push(`${name} upper limit must be a finite number.`);
          if (number(a) && number(b) && Number(a) >= Number(b)) messages.push(`${name} lower limit must be less than the upper limit.`);
        }
      }
      show(key + "-error", messages, [low, high]);
      if (messages.length && !firstBad) firstBad = !a || !number(a) ? low : high;
    }
    const hold = form.elements.hold_s, text = hold.value.trim();
    const holdMessages = !text ? ["Enter the sustained duration in seconds."] :
      !number(text) ? ["The sustained duration must be a finite number of seconds."] :
      Number(text) <= 0 ? ["The sustained duration must be positive."] : [];
    show("hold_s-error", holdMessages, [hold]);
    if (holdMessages.length && !firstBad) firstBad = hold;
    if (firstBad) { event.preventDefault(); firstBad.focus(); }
  });
}

// ---------- system ----------
function pathRow(key, tone, state, when, detail) {
  const row = $("path-" + key);
  setTone(row.querySelector("[data-cell=state]"), tone, state);
  row.querySelector("[data-cell=when]").textContent = when;
  row.querySelector("[data-cell=detail]").textContent = detail;
}
function renderSystem(v) {
  const {health: h, status, current, timing, since} = v;
  const unknown = "Unknown, monitor overdue";
  const known = part => part.state !== "unknown" || !status;
  const m = h.monitor;
  pathRow("monitor", m.state === "current" ? "green" : m.state === "overdue" ? "red" : "none",
    m.state === "current" ? "Running" : m.state === "overdue" ? "Overdue" : "Waiting", m.age_s == null ? "—" : ago(m.age_s),
    `Checks faults every ${timing.fault_check_interval_s} s`);
  const s = h.serial;
  const commAlert = s.communication_alert_active && s.communication_timed_out;
  const ackDue = current && status.communication_alert_id && status.communication_timed_out === false;
  pathRow("serial", !known(s) ? "none" : commAlert || s.state === "disconnected" ? "red" : ackDue ? "amber" : s.state === "connected" ? "green" : "none",
    !known(s) ? unknown : commAlert ? "No contact, alert active" : ackDue ? "Connected, alert to acknowledge" : word(s.state).replace(/^./, c => c.toUpperCase()),
    s.last_contact_age_s == null ? "—" : ago(s.last_contact_age_s), s.error || "USB serial from the ESP32");
  const b = h.bme680;
  pathRow("bme680", !known(b) ? "none" : b.alert_active ? "red" : b.measurement_current ? "green" : "amber",
    !known(b) ? unknown : b.alert_active ? "Readings missing, alert active" : b.measurement_current ? "Readings current" : "Readings " + word(b.state),
    b.measurement_age_s == null ? "—" : ago(b.measurement_age_s),
    status?.air_quality ? `Bosch accuracy ${status.air_quality.accuracy ?? "unknown"} of 3 · gas sensor ${word(status.gas_calibration)}` : "—");
  const d = h.dust;
  const baseline = status?.dust_ugm3 ? (status.dust_ugm3.state === "establishing_baseline" ? "Establishing baseline" : "Baseline established") : "—";
  pathRow("dust", !known(d) ? "none" : d.alert_active ? "red" : d.state === "fresh" ? "green" : "amber",
    !known(d) ? unknown : d.alert_active ? "Readings missing, alert active" : d.state === "fresh" ? "Readings current" : "Readings " + word(d.state),
    d.age_s == null ? "—" : ago(d.age_s), baseline);
  const o = h.occupancy;
  pathRow("occupancy", !known(o) ? "none" : o.state === "occupied" ? "green" : o.state === "unknown" ? "amber" : "none",
    !known(o) ? unknown : o.state === "occupied" ? "Room occupied" : o.state === "unknown" ? "Occupancy unknown" : "Room not occupied",
    o.observation_age_s == null ? "—" : ago(o.observation_age_s),
    o.source === "camera" ? `Checks every ${timing.camera_interval_s} s, images are not stored` :
    o.source === "simulated" ? "Simulated occupancy, no camera in use" : o.source === "none" ? "No camera configured" : "—");
  const p = h.profile;
  pathRow("profile", !known(p) ? "none" : p.state === "loaded" ? "green" : p.state === "error" ? "red" : "amber",
    !known(p) ? unknown : p.state === "loaded" ? "Loaded" : p.state === "error" ? "Could not be read" : "No limits saved",
    "—", p.error || (v.profile?.label ? `Label "${v.profile.label}"` : v.profile ? "No label set" : "No patient limits saved"));
  const a = h.alarm, alarm = alarmState(v);
  pathRow("alarm", known(a) ? alarm.tone : "none", known(a) ? alarm.chip : unknown,
    a.confirmation_age_s == null ? "—" : ago(a.confirmation_age_s),
    a.confirmed_level == null ? "No confirmation from the board" : `${ALARM_LEVEL[a.confirmed_level]}, confirmed by the board · level ${a.confirmed_level} of 2`);
  const retained = current && status.measurement_current ? "" : status ? " (retained)" : "";
  const gas = status?.last_reading?.gas_ohms;
  $("gas_ohms").textContent = gas == null ? "—" : (gas / 1000).toFixed(1) + " kΩ" + retained;
  const mv = status?.dust?.sensor_mv;
  $("dust_mv").textContent = mv == null ? "—" : Math.round(mv) + " mV" + (current ? "" : " (retained)");
  const base = status?.dust_ugm3?.baseline_mv;
  $("dust-baseline").textContent = base == null ? (status ? "not established yet" : "—") : Math.round(base) + " mV";
  const acc = status?.air_quality?.accuracy;
  $("bosch-accuracy").textContent = acc == null ? "—" : acc + " of 3" + (acc < 3 && status.air_quality.state === "calibrating" ? ", calibrating" : "");
  for (const node of document.querySelectorAll("[data-timing]")) {
    const key = node.dataset.timing, value = timing[key];
    node.textContent = value == null ? "—" : key.endsWith("_days") ? value + (value === 1 ? " day" : " days") : value + " s";
  }
  void since;
}

// ---------- refresh loop ----------
let latest = null, refreshSeconds = 10, refreshId = 0, timer = null;
function apiUrl() {
  if (PAGE === "events") return "/api/room?limit=50";
  if (PAGE === "trends") return "/api/room?limit=20&window=" + trendWindow;
  return "/api/room?limit=20";
}
function render() {
  if (!latest) return;
  const v = latest;
  renderTop(v);
  renderAttention(v, false);
  if (PAGE === "index") { renderTiles(v); renderOverviewChart(v); renderRecent(v); }
  else if (PAGE === "trends") renderTrends(v);
  else if (PAGE === "events") renderEvents(v);
  else if (PAGE === "limits") renderLimits(v);
  else if (PAGE === "system") renderSystem(v);
}
async function refresh() {
  const id = ++refreshId;
  clearTimeout(timer);
  try {
    const response = await fetch(apiUrl(), {cache: "no-store"});
    if (!response.ok) throw new Error("Dashboard data unavailable");
    const data = await response.json();
    if (id !== refreshId) return;
    latest = derive(data);
    refreshSeconds = data.timing.dashboard_refresh_s || 10;
    if (PAGE === "events") {
      if (!eventList.length) eventsMore = data.events_has_more;
      mergeEvents(data.events);
    }
    render();
  } catch (error) {
    if (id !== refreshId) return;
    $("connection").textContent = "Dashboard data unavailable · retrying";
    setTone($("connection-dot"), "red");
    $("silence").hidden = true;
    $("ack").hidden = true;
    renderAttention(null, true);
  } finally {
    if (id === refreshId) timer = setTimeout(refresh, refreshSeconds * 1000);
  }
}

function pressGroup(buttons, chosen) {
  for (const button of buttons) button.setAttribute("aria-pressed", String(button === chosen));
}
function wire() {
  if (PAGE === "index") {
    const buttons = document.querySelectorAll(".chart-card .seg button");
    for (const button of buttons) button.addEventListener("click", () => {
      overviewMetric = button.dataset.metric;
      pressGroup(buttons, button);
      if (latest) renderOverviewChart(latest);
    });
  }
  if (PAGE === "trends") {
    const buttons = document.querySelectorAll("[data-window]");
    pressGroup(buttons, [...buttons].find(button => button.dataset.window === trendWindow));
    for (const button of buttons) button.addEventListener("click", () => {
      if (trendWindow === button.dataset.window) return;
      trendWindow = button.dataset.window;
      pressGroup(buttons, button);
      history.replaceState(null, "", trendWindow === "7d" ? "?window=7d" : location.pathname);
      refresh();
    });
  }
  if (PAGE === "events") {
    const buttons = document.querySelectorAll("[data-family]");
    for (const button of buttons) button.addEventListener("click", () => {
      eventFilter = button.dataset.family;
      pressGroup(buttons, button);
      if (latest) renderEvents(latest);
    });
    $("older").addEventListener("click", async () => {
      if (loadingOlder || !eventList.length) return;
      loadingOlder = true;
      $("older").disabled = true;
      $("older").textContent = "Loading older events";
      try {
        const oldest = eventList[eventList.length - 1].id;
        const response = await fetch(`/api/room?events_before=${oldest}&limit=50`, {cache: "no-store"});
        if (!response.ok) throw new Error("unavailable");
        const data = await response.json();
        mergeEvents(data.events);
        eventsMore = data.events_has_more;
        if (latest) renderEvents(latest);
      } catch {
        $("event-count").textContent = "Older events could not be loaded. Try again.";
      } finally {
        loadingOlder = false;
        $("older").disabled = false;
        $("older").textContent = "Show older events";
      }
    });
  }
  if (PAGE === "limits") wireLimitsForm();
  // Charts are drawn at their container's pixel size; redraw when that size changes.
  const widths = new WeakMap();
  let resizeTimer = null;
  const observer = new ResizeObserver(entries => {
    let changed = false;
    for (const entry of entries) {
      const width = Math.round(entry.contentRect.width);
      if (widths.has(entry.target) && widths.get(entry.target) !== width) changed = true;
      widths.set(entry.target, width);
    }
    if (!changed) return;
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => { if (latest) render(); }, 100);
  });
  for (const chart of document.querySelectorAll(".chart")) observer.observe(chart);
}
wire();
refresh();
