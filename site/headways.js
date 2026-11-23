// Shared helpers for the "How often they run" tables: one row per route, both directions combined.
//   HW.combine(rows, order) -> [{route, peak, midday, offpeak, overnight, hours}]
// rows come from the data files: one per route and direction, with headways in minutes and first/last
// departures as "HH:MM" clock times (service can run past midnight, so last may be earlier than first).
window.HW = (function () {
  const toMin = s => { const [h, m] = s.split(":").map(Number); return (h % 24) * 60 + m; };
  const fmtHour = h => h === 0 ? "12am" : h < 12 ? h + "am" : h === 12 ? "12pm" : (h - 12) + "pm";

  // Service hours across all directions. "24h" if the longest gap with no departures is 1 hour or less;
  // otherwise the span rounded inward to whole hours (start rounded up, end rounded down).
  function hours(rows) {
    const on = new Uint8Array(1440);
    rows.forEach(r => {
      if (!r.first || !r.last) return;
      let k = toMin(r.first); const end = toMin(r.last);
      for (let n = 0; n < 1440; n++) { on[k] = 1; if (k === end) break; k = (k + 1) % 1440; }
    });
    let best = 0, bestStart = 0, run = 0, start = 0;
    for (let i = 0; i < 2880 && run < 1440; i++) {
      if (on[i % 1440]) { run = 0; continue; }
      if (run === 0) start = i;
      run++;
      if (run > best) { best = run; bestStart = start; }
    }
    if (best <= 60) return "24h";
    const firstOn = (bestStart + best) % 1440, lastOn = (bestStart + 1439) % 1440;
    return fmtHour(Math.ceil(firstOn / 60) % 24) + "–" + fmtHour(Math.floor(lastOn / 60));
  }

  // One number per window: the two directions' average, rounded, when they differ by 5 minutes or less
  // (7 and 8 -> 8); the range only for outliers that differ by more (evening 22 and 39 -> "22–39").
  // "—" when there is no service in that window.
  function range(vals) {
    const v = vals.filter(x => x != null);
    if (!v.length) return "—";
    const lo = Math.min(...v), hi = Math.max(...v);
    if (hi - lo <= 5) return String(Math.round(v.reduce((a, b) => a + b, 0) / v.length));
    return `${lo}–${hi}`;
  }

  // Values set by hand where the schedule is irregular. Line 10 peak: gaps of 12-15 minutes (average about 13.5);
  // shown as 15, its typical scheduled gap (owner's choice, 2026-11-23).
  const OVERRIDES = { "10": { peak: "15" } };

  // Overnight (midnight-4 AM): a number only where departures cover the whole window. "58 (one way)" when only one
  // direction does; "until 1:05" / "from 3:40" when service stops or starts inside the window; "—" when none.
  function night(rs) {
    const nums = rs.map(r => r.overnight).filter(x => x != null);
    if (nums.length) return range(nums) + (nums.length < rs.length ? " (one way)" : "");
    const toM = t => { const [h, m] = t.split(":").map(Number); return h * 60 + m; };
    const from = rs.map(r => r.overnight_from).filter(Boolean).sort((a, b) => toM(a) - toM(b));
    const clock = t => { const [h, m] = t.split(":").map(Number); return `${h % 12 === 0 ? 12 : h % 12}:${String(m).padStart(2, "0")}${h < 12 ? "am" : "pm"}`; };
    if (from.length) return "from " + clock(from[0]);
    const until = rs.map(r => r.overnight_until).filter(Boolean).sort((a, b) => toM(b) - toM(a));
    if (until.length) return "until " + clock(until[0]);
    return "—";
  }

  function combine(rows, order) {
    const by = new Map();
    rows.forEach(r => { if (!by.has(r.route)) by.set(r.route, []); by.get(r.route).push(r); });
    const keys = [...by.keys()];
    if (order) keys.sort((a, b) => order.indexOf(a) - order.indexOf(b));
    return keys.map(route => {
      const rs = by.get(route);
      return Object.assign({ route, peak: range(rs.map(r => r.peak)), midday: range(rs.map(r => r.midday)),
               offpeak: range(rs.map(r => r.offpeak)), overnight: night(rs), hours: hours(rs) }, OVERRIDES[route] || {});
    });
  }
  return { combine, hours, range, night };
})();
