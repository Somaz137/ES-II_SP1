// Line charts as inline SVG: configured band, gaps left as gaps, outside-limit stretches in red.
"use strict";
const RoomChart = (() => {
  const NS = "http://www.w3.org/2000/svg";
  const COLOR = {line: "#12805c", band: "#d8f0e6", red: "#c62828", gap: "#eceff0", grid: "#e3ebe7", muted: "#51635b"};
  let clipCount = 0;

  function el(name, attrs, parent) {
    const node = document.createElementNS(NS, name);
    for (const [key, value] of Object.entries(attrs || {})) node.setAttribute(key, value);
    if (parent) parent.append(node);
    return node;
  }
  function text(parent, x, y, content, attrs) {
    const node = el("text", {x, y, ...attrs}, parent);
    node.textContent = content;
    return node;
  }
  const clock = at => new Date(at * 1000).toLocaleTimeString("en-GB", {hour: "2-digit", minute: "2-digit"});
  const dayName = at => new Date(at * 1000).toLocaleDateString("en-GB", {weekday: "short", day: "numeric"});

  // Round tick values for the value axis.
  function niceTicks(min, max, count) {
    const span = max - min || 1;
    const raw = span / count;
    const power = 10 ** Math.floor(Math.log10(raw));
    const step = [1, 2, 2.5, 5, 10].map(f => f * power).find(s => s >= raw) || raw;
    const ticks = [];
    for (let v = Math.ceil(min / step) * step; v <= max + 1e-9; v += step) ticks.push(+v.toFixed(6));
    return ticks;
  }

  // Ticks for the shared time axis: every 4 hours for a day, each midnight for a week.
  function timeTicks(start, end) {
    const ticks = [];
    const week = end - start > 2 * 86400;
    const first = new Date(start * 1000);
    first.setMinutes(0, 0, 0);
    if (week) first.setHours(0); else first.setHours(Math.ceil(first.getHours() / 4) * 4);
    for (let d = first; d.getTime() / 1000 <= end; d = new Date(d.getTime() + (week ? 86400e3 : 4 * 3600e3))) {
      if (week) d.setHours(0, 0, 0, 0);
      const at = d.getTime() / 1000;
      if (at >= start) ticks.push({at, label: week ? dayName(at) : clock(at)});
    }
    return ticks;
  }

  // Split buckets into runs; a missing stretch longer than two buckets is a gap.
  function runs(buckets, bucketS) {
    const out = [];
    let run = [];
    for (const bucket of buckets) {
      if (run.length && bucket.at - run[run.length - 1].at > 2 * bucketS) { out.push(run); run = []; }
      run.push(bucket);
    }
    if (run.length) out.push(run);
    return out;
  }

  // Stretches without data of at least `minS` seconds, including before the first and after the last bucket.
  function gaps(buckets, start, end, bucketS, minS) {
    const out = [];
    let previous = start;
    for (const bucket of buckets) {
      if (bucket.at - previous >= minS) out.push([previous, bucket.at]);
      previous = bucket.at + bucketS;
    }
    if (end - previous >= minS) out.push([previous, end]);
    return out;
  }

  function outside(value, low, high) {
    return (high != null && value > high) || (low != null && value < low);
  }

  /*
   * opts: buckets, start, end, bucketS, low, high, digits, unit, name,
   *       small (no axes), alertLabel (red text, e.g. "above limit · 12 min")
   */
  function draw(container, opts) {
    const width = Math.max(120, container.clientWidth);
    const height = Math.max(60, container.clientHeight);
    const small = !!opts.small;
    const m = small ? {l: 0, r: 0, t: 6, b: 6} : {l: 44, r: 44, t: 12, b: 26};
    const plotW = width - m.l - m.r, plotH = height - m.t - m.b;
    const {buckets, start, end, bucketS, low, high} = opts;
    const svg = el("svg", {viewBox: `0 0 ${width} ${height}`, width, height, role: "img"});
    const x = at => m.l + plotW * (at - start) / (end - start);

    const values = buckets.flatMap(b => [b.min, b.max]);
    const limits = [low, high].filter(v => v != null);
    let lo = Math.min(...values, ...limits), hi = Math.max(...values, ...limits);
    if (!isFinite(lo)) { lo = 0; hi = 1; }
    const pad = (hi - lo) * .12 || Math.abs(hi) * .05 || 1;
    lo -= pad; hi += pad;
    if (low == null && high != null && lo > 0 && Math.min(...values, high) >= 0) lo = Math.max(0, lo);
    const y = v => m.t + plotH * (1 - (v - lo) / (hi - lo));

    // Configured band.
    if (limits.length) {
      const top = y(high != null ? high : hi), bottom = y(low != null ? low : lo);
      el("rect", {x: m.l, y: top, width: plotW, height: Math.max(0, bottom - top), fill: COLOR.band}, svg);
    }
    if (!small) {
      for (const tick of niceTicks(lo, hi, 4)) {
        el("line", {x1: m.l, x2: m.l + plotW, y1: y(tick), y2: y(tick), stroke: COLOR.grid}, svg);
        text(svg, m.l - 8, y(tick) + 4, tick.toLocaleString("en-GB", {maximumFractionDigits: 2}), {"text-anchor": "end"});
      }
      for (const [value, word] of [[high, "upper"], [low, "lower"]]) {
        if (value != null) text(svg, m.l + plotW + 6, y(value) + 4, value.toFixed(opts.digits),
          {style: `fill:${COLOR.line}`, "font-weight": 600, "aria-label": word + " limit"});
      }
      for (const tick of timeTicks(start, end)) {
        const anchor = x(tick.at) < m.l + 20 ? "start" : x(tick.at) > m.l + plotW - 20 ? "end" : "middle";
        text(svg, x(tick.at), height - 6, tick.label, {"text-anchor": anchor});
      }
    }
    // Gaps: shaded and labelled, never joined.
    const minGap = Math.max(10 * bucketS, (end - start) / 60);
    for (const [from, to] of gaps(buckets, start, end, bucketS, minGap)) {
      const gx = x(from), gw = x(to) - x(from);
      el("rect", {x: gx, y: m.t, width: gw, height: plotH, fill: COLOR.gap}, svg);
      if (gw > 56 && !small) text(svg, gx + gw / 2, m.t + 16, "no data", {"text-anchor": "middle"});
      else if (gw > 56 && small && !buckets.length) text(svg, gx + gw / 2, m.t + plotH / 2 + 4, "no data", {"text-anchor": "middle"});
    }
    // Line, then the same line in red, clipped to the regions outside the limits.
    const paths = runs(buckets, bucketS).map(run => run.length === 1 ?
      `M${x(run[0].at) - 1.5},${y(run[0].avg)}h3` :
      run.map((b, i) => (i ? "L" : "M") + x(b.at).toFixed(1) + "," + y(b.avg).toFixed(1)).join(""));
    const d = paths.join("");
    if (d) {
      el("path", {d, fill: "none", stroke: COLOR.line, "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round"}, svg);
      if (limits.length) {
        const id = "out-" + (++clipCount);
        const clip = el("clipPath", {id}, el("defs", {}, svg));
        if (high != null) el("rect", {x: 0, y: 0, width, height: Math.max(0, y(high)), fill: "#000"}, clip);
        if (low != null) el("rect", {x: 0, y: y(low), width, height: Math.max(0, height - y(low)), fill: "#000"}, clip);
        el("path", {d, fill: "none", stroke: COLOR.red, "stroke-width": 2.5, "stroke-linejoin": "round",
          "stroke-linecap": "round", "clip-path": `url(#${id})`}, svg);
      }
      const last = buckets[buckets.length - 1];
      const lastRed = outside(last.avg, low, high);
      el("circle", {cx: x(last.at), cy: y(last.avg), r: 4, fill: lastRed ? COLOR.red : COLOR.line, stroke: "#fff", "stroke-width": 2}, svg);
    }
    if (opts.alertLabel) {
      // Small multiples label at the left so the label never covers the newest readings.
      text(svg, small ? m.l + 6 : m.l + plotW - 12, m.t + 14, opts.alertLabel,
        {"text-anchor": small ? "start" : "end", style: `fill:${COLOR.red}`, "font-weight": 600});
    } else if (opts.noteLabel) {
      text(svg, m.l + 4, m.t + 14, opts.noteLabel, {"text-anchor": "start"});
    }
    svg.setAttribute("aria-label", opts.summary || opts.name);
    container.replaceChildren(svg);
    addHover(container, svg, buckets, x, y, opts, m, plotH);
  }

  // Crosshair and tooltip for pointer users; the summary table is the accessible equivalent.
  function addHover(container, svg, buckets, x, y, opts, m, plotH) {
    if (!buckets.length) return;
    const g = el("g", {visibility: "hidden", "pointer-events": "none"}, svg);
    const line = el("line", {y1: m.t, y2: m.t + plotH, stroke: COLOR.muted, "stroke-dasharray": "3 3"}, g);
    const dot = el("circle", {r: 4, fill: COLOR.line, stroke: "#fff", "stroke-width": 2}, g);
    const tip = document.createElement("div");
    tip.className = "tip";
    tip.hidden = true;
    const hit = el("rect", {x: m.l, y: 0, width: Math.max(0, x(opts.end) - m.l), height: svg.viewBox.baseVal.height, fill: "transparent"}, svg);
    hit.addEventListener("pointermove", event => {
      const box = svg.getBoundingClientRect();
      const px = (event.clientX - box.left) * (svg.viewBox.baseVal.width / box.width);
      let best = buckets[0];
      for (const b of buckets) if (Math.abs(x(b.at) - px) < Math.abs(x(best.at) - px)) best = b;
      if (Math.abs(x(best.at) - px) > 24) { g.setAttribute("visibility", "hidden"); tip.hidden = true; return; }
      const bx = x(best.at), by = y(best.avg);
      line.setAttribute("x1", bx); line.setAttribute("x2", bx);
      dot.setAttribute("cx", bx); dot.setAttribute("cy", by);
      dot.setAttribute("fill", outside(best.avg, opts.low, opts.high) ? COLOR.red : COLOR.line);
      g.setAttribute("visibility", "visible");
      const f = v => v.toFixed(opts.digits);
      const when = opts.end - opts.start > 2 * 86400 ? dayName(best.at) + " " + clock(best.at) : clock(best.at);
      tip.textContent = `${when} · ${f(best.avg)}\u00a0${opts.unit}`.trim() +
        (best.min !== best.max ? ` (${f(best.min)} to ${f(best.max)})` : "");
      tip.hidden = false;
      const scale = box.width / svg.viewBox.baseVal.width;
      const left = bx * scale;
      tip.style.left = Math.min(Math.max(0, left - tip.offsetWidth / 2), box.width - tip.offsetWidth) + "px";
      tip.style.top = Math.max(0, by * scale - 40) + "px";
    });
    hit.addEventListener("pointerleave", () => { g.setAttribute("visibility", "hidden"); tip.hidden = true; });
    container.append(tip);
  }

  return {draw, timeTicks, clock, dayName, outside};
})();
