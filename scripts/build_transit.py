#!/usr/bin/env python3
"""Build site/transit/data/transit.json: transit lines through Silver Lake NC.

Inputs (downloaded here, never committed):
  * LA Metro GTFS bus + rail feeds (gitlab.com/LACMTA/gtfs_bus, gtfs_rail)
  * Silver Lake NC boundary, Neighborhood Councils (Certified) layer (maps.lacity.org, via LA GeoHub)

The NC boundary is the City's official one (LA GeoHub "Neighborhood Councils (Certified)").

Needs: pip install shapely
"""
import csv, datetime as dt, io, json, math, os, statistics, sys, tempfile, urllib.parse, urllib.request, zipfile
from collections import Counter, defaultdict

from shapely.geometry import LineString, Point, mapping
from shapely.ops import substring, unary_union

BUS_ROUTES = {"2": "2-13201", "4": "4-13201", "10": "10-13201", "92": "92-13201", "93": "93-13201", "182": "182-13201", "296": "296-13201",
              # nearby routes just outside the NC (drawn dashed on the page)
              "14": "14-13201", "204": "204-13201", "754": "754-13201"}
DASH_ROUTES = {"DASH": "4869", "DASH-LF": "4577"}   # LADOT DASH Pico Union/Echo Park (not in the Metro feed); DASH-LF = Observatory/Los Feliz
BUS_COLORS = {"2": "#d95f02", "4": "#1b9e77", "10": "#7570b3", "92": "#e7298a", "93": "#a6761d", "182": "#66a61e", "296": "#444444", "DASH": "#e6ab02",
              "14": "#8e44ad", "204": "#2c7fb8", "754": "#08306b", "DASH-LF": "#795548"}
RAIL_ROUTE, RAIL_COLOR = "802", "#eb131b"  # B Line
D_ROUTE, D_COLOR = "805", "#a05da5"        # D Line (shares Westlake/MacArthur Park with the B Line)
# Corridor view: Bus 2 down Alvarado to the D Line at Westlake/MacArthur Park (south of the NC)
CORRIDOR_VIEW = (-118.2985, 34.0440, -118.2300, 34.1130)   # minx, miny, maxx, maxy: out to Union Station
CORRIDOR_ROUTES = {"2", "4", "B", "D", "E"}   # lines drawn on the corridor map
RAIL_ALL = {"801": "A", "802": "B", "803": "C", "804": "E", "805": "D", "807": "K"}   # all Metro rail, for transfers
NO_HEADWAY = {"A", "C", "E", "K"}   # rail lines not shown in the headway tables
UNION_STATION = (-118.234249, 34.056197)   # B and D Lines end here; trim their shapes
TRANSFER_M = 350   # bus stop within this of a rail station = transfer
REF_STOP_NAME = {"D": "Westlake / MacArthur Park Station"}   # headway measured here, not nearest the NC
GITLAB = "https://gitlab.com/LACMTA/{}/-/raw/master/{}"
LADOT_GTFS = "https://ladotbus.com/gtfs"   # LADOT DASH feed; see their GTFS developer license
OUT = os.path.join(os.path.dirname(__file__), "..", "site", "transit", "data", "transit.json")
MARGIN_DEG = 0.010        # ~1 km of context around the NC outline (shows the Echo Park DASH)
# Headways: measured on one typical weekday (override with HEADWAY_DATE=YYYY-MM-DD).
# Windows are hours of the service day. Peak = AM + PM; off-peak = early morning + evening/night.
# Hours >= 24 are after midnight on the same service day (GTFS times run past 24:00), so 2-5 AM is both 2-5 and 26-29.
WINDOWS = {"peak": [(6, 9), (15, 19)], "midday": [(9, 15)],
           "offpeak": [(0, 2), (5, 6), (19, 26), (29, 30)], "overnight": [(2, 5), (26, 29)]}
WINDOW_TEXT = {"peak": "6-9 AM and 3-7 PM", "midday": "9 AM-3 PM", "offpeak": "5-6 AM and 7 PM-2 AM",
               "overnight": "2-5 AM"}
MAX_WALK_M = 1000         # list nearest stop of each route within this walk of a B Line station


def fetch(url, dest, tries=5):
    """Download url to dest, retrying with backoff on rate limits (429) and server errors."""
    import time, urllib.error
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=300) as r, open(dest, "wb") as f:
                while chunk := r.read(1 << 20):
                    f.write(chunk)
            return
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504) or i == tries - 1:
                raise
            wait = int(e.headers.get("Retry-After") or 0) or 15 * (i + 1)
            print(f"  {e.code} on {url}; retrying in {wait}s", file=sys.stderr)
            time.sleep(wait)


def rows(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        yield from csv.DictReader(f)


def meters(a, b):
    dy = (a[1] - b[1]) * 111_320
    dx = (a[0] - b[0]) * 111_320 * math.cos(math.radians(a[1]))
    return math.hypot(dx, dy)


NC_LAYER = "https://maps.lacity.org/lahub/rest/services/Boundaries/MapServer/18"   # Neighborhood Councils (Certified), LA GeoHub


def boundary():
    """Official Silver Lake NC boundary from the City's Neighborhood Councils (Certified) layer (LA GeoHub)."""
    q = urllib.parse.urlencode({"where": "NAME = 'SILVER LAKE NC'", "outFields": "NAME,NC_ID", "returnGeometry": "true",
                                "outSR": "4326", "f": "geojson"})
    req = urllib.request.Request(NC_LAYER + "/query?" + q, headers={"User-Agent": "slnc-transit-map/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        feats = json.load(r).get("features") or []
    if not feats:
        raise SystemExit("Silver Lake NC boundary not found in " + NC_LAYER)
    from shapely.geometry import shape
    poly = shape(feats[0]["geometry"])
    if poly.geom_type != "Polygon":
        poly = max(poly.geoms, key=lambda g: g.area)
    return poly, ("Official boundary: Neighborhood Councils (Certified), City of Los Angeles "
                  f"(LA GeoHub, NC_ID {feats[0]['properties'].get('NC_ID')}).")


def service_date(feeds=()):
    """A typical Wednesday to measure headways on: the first one at least 10 days out (avoids holiday weeks) on which
    every feed in `feeds` has service; earlier Wednesdays are the fallback when a feed's calendar ends sooner."""
    if os.environ.get("HEADWAY_DATE"):
        return dt.date.fromisoformat(os.environ["HEADWAY_DATE"])
    today = dt.date.today()
    weds = [today + dt.timedelta(days=k) for k in range(70) if (today + dt.timedelta(days=k)).weekday() == 2]
    soon = today + dt.timedelta(days=10)
    for d in [w for w in weds if w >= soon] + [w for w in reversed(weds) if w < soon]:
        if all(active_services(f, d) for f in feeds):
            return d
    return weds[0]


def active_services(feed_dir, day):
    """service_ids running on `day`, from calendar.txt + calendar_dates.txt."""
    ymd = day.strftime("%Y%m%d")
    col = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"][day.weekday()]
    on = set()
    cal = os.path.join(feed_dir, "calendar.txt")
    if os.path.exists(cal):
        for r in rows(cal):
            if r[col] == "1" and r["start_date"] <= ymd <= r["end_date"]:
                on.add(r["service_id"])
    cd = os.path.join(feed_dir, "calendar_dates.txt")
    if os.path.exists(cd):
        for r in rows(cd):
            if r["date"] == ymd:
                (on.add if r["exception_type"] == "1" else on.discard)(r["service_id"])
    return on


def secs(t):
    h, m, sec = t.split(":")
    return int(h) * 3600 + int(m) * 60 + int(sec)


def hhmm(sec):
    return f"{(sec // 3600) % 24:02d}:{(sec % 3600) // 60:02d}"


def headways(deps):
    """Median minutes between consecutive departures inside each window, per category.
    Overnight (2-5 AM) only counts as service when departures cover the whole window: no stretch of more than an
    hour without one, counting from 2:00 and to 5:00. Otherwise it is None, with overnight_from / overnight_until
    giving the first or last departure in the window (e.g. trains that start at 4:24)."""
    deps = sorted(deps)
    out = {}
    for cat, spans in WINDOWS.items():
        gaps = []
        for lo, hi in spans:
            seg = [t for t in deps if lo * 3600 <= t < hi * 3600]
            gaps += [(b - a) / 60 for a, b in zip(seg, seg[1:])]
        out[cat] = round(statistics.median(gaps)) if gaps else None
    night = sorted({(t % 86400) // 60 for t in deps if any(lo * 3600 <= t < hi * 3600 for lo, hi in WINDOWS["overnight"])})
    out["overnight_from"] = out["overnight_until"] = None
    if night:
        start, end = WINDOWS["overnight"][0][0] * 60, WINDOWS["overnight"][0][1] * 60
        inner = [b - a for a, b in zip(night, night[1:])]
        if max([night[0] - start, end - night[-1]] + inner) > 60:
            out["overnight"] = None
            if night[0] - start > 60:
                out["overnight_from"] = f"{night[0] // 60}:{night[0] % 60:02d}"
            if end - night[-1] > 60:
                out["overnight_until"] = f"{night[-1] // 60}:{night[-1] % 60:02d}"
        else:
            out["overnight"] = round(statistics.median(inner)) if inner else None
    return out


def main():
    tmp = tempfile.mkdtemp(prefix="gtfs_")
    bus, rail, dash = (os.path.join(tmp, n) for n in ("bus", "rail", "dash"))
    for d_ in (bus, rail, dash):
        os.makedirs(d_)
    print("downloading GTFS…", file=sys.stderr)
    fetch(GITLAB.format("gtfs_bus", "gtfs_bus.zip"), os.path.join(tmp, "bus.zip"))
    zipfile.ZipFile(os.path.join(tmp, "bus.zip")).extractall(bus)
    fetch(LADOT_GTFS, os.path.join(tmp, "dash.zip"))
    zipfile.ZipFile(os.path.join(tmp, "dash.zip")).extractall(dash)
    for f in ("routes", "trips", "shapes", "stops", "stop_times", "calendar", "calendar_dates"):
        fetch(GITLAB.format("gtfs_rail", f + ".txt"), os.path.join(rail, f + ".txt"))

    nc, nc_note = boundary()
    minx, miny, maxx, maxy = nc.bounds
    view = (minx - MARGIN_DEG, miny - MARGIN_DEG, maxx + MARGIN_DEG, maxy + MARGIN_DEG)
    # B Line runs under Vermont Ave, west of the NC: widen the window to include it.
    view = (min(view[0], -118.2935), view[1], view[2], view[3])
    from shapely.geometry import box
    window = box(*view)

    lines, all_stops, hw_rows = [], {}, []
    corr_lines, corr_stops = [], {}
    win2 = box(*CORRIDOR_VIEW)
    day = service_date((bus, rail, dash))
    feeds = [(bus, dict((rid, k) for k, rid in BUS_ROUTES.items()), "bus"),
             (dash, dict((rid, k) for k, rid in DASH_ROUTES.items()), "bus"),
             (rail, RAIL_ALL, "rail")]
    for d, wanted, mode in feeds:
        trips = defaultdict(Counter)   # route_id -> (shape_id, dir) -> n
        trip_route, trip_info = {}, {}
        on_day = active_services(d, day)
        for t in rows(os.path.join(d, "trips.txt")):
            if t["route_id"] in wanted:
                trips[t["route_id"]][(t["shape_id"], t.get("direction_id", ""))] += 1
                trip_route[t["trip_id"]] = t["route_id"]
                if t["service_id"] in on_day:
                    trip_info[t["trip_id"]] = (t["route_id"], t.get("direction_id", ""), t.get("trip_headsign", ""))
        keep = {}
        for rid, cnt in trips.items():
            by_dir = defaultdict(list)
            for (sid, dr), n in cnt.most_common():
                by_dir[dr].append(sid)
            keep[rid] = {sid for lst in by_dir.values() for sid in lst[:3]}  # 3 main patterns/direction
        want_shapes = {s for v in keep.values() for s in v}
        shp = defaultdict(list)
        for r in rows(os.path.join(d, "shapes.txt")):
            if r["shape_id"] in want_shapes:
                shp[r["shape_id"]].append((int(r["shape_pt_sequence"]), float(r["shape_pt_lon"]), float(r["shape_pt_lat"])))
        seen, seen2 = set(), set()
        for rid, sids in keep.items():
            label = wanted[rid]
            for sid in sorted(sids):
                ls = LineString([(x, y) for _, x, y in sorted(shp[sid])])
                if label in CORRIDOR_ROUTES:
                    lsc = ls
                    if label in ("B", "D") and ls.distance(Point(UNION_STATION)) < 0.0008:
                        # the shape runs on into the rail yard: keep only the part up to Union Station
                        cut = ls.project(Point(UNION_STATION))
                        halves = [substring(ls, 0, cut), substring(ls, cut, ls.length)]
                        halves = [h_ for h_ in halves if h_.geom_type == "LineString" and h_.length > 0]
                        lsc = min(halves, key=lambda h_: h_.bounds[2])   # the half that heads west
                    c2 = lsc.intersection(win2)
                    for part in (c2.geoms if hasattr(c2, "geoms") else [c2]):
                        if part.geom_type != "LineString" or part.length == 0:
                            continue
                        # the part inside the main map window is solid; the continuation beyond it is dotted
                        for geom, ext in ((part.intersection(window), False), (part.difference(window), True)):
                            for g in (geom.geoms if hasattr(geom, "geoms") else [geom]):
                                if g.geom_type != "LineString" or g.length == 0:
                                    continue
                                cs2 = list(g.coords)
                                k2 = (label, ext, tuple(sorted((round(cs2[0][0], 4), round(cs2[0][1], 4),
                                                                round(cs2[-1][0], 4), round(cs2[-1][1], 4)))))
                                if k2 not in seen2:
                                    seen2.add(k2)
                                    corr_lines.append({"route": label, "mode": mode, "ext": ext or mode == "rail",
                                                       "coords": [[round(x, 5), round(y, 5)] for x, y in g.simplify(0.00003).coords]})
                clipped = ls.intersection(window)
                if clipped.is_empty:
                    continue
                inside = ls.intersection(nc)
                for part in (clipped.geoms if hasattr(clipped, "geoms") else [clipped]):
                    if part.geom_type != "LineString" or part.length == 0:
                        continue
                    cs = list(part.coords)
                    key = (label, tuple(sorted((round(cs[0][0], 4), round(cs[0][1], 4),
                                                round(cs[-1][0], 4), round(cs[-1][1], 4)))))
                    if key in seen:
                        continue
                    seen.add(key)
                    lines.append({"route": label, "mode": mode,
                                  "coords": [[round(x, 5), round(y, 5)] for x, y in part.simplify(0.00003).coords],
                                  "in_nc": part.intersection(nc).length > 0})
        # stops served inside the window
        stop_routes = defaultdict(set)
        trip_ids = set(trip_route)
        pos = {s["stop_id"]: (float(s["stop_lon"]), float(s["stop_lat"]), s["stop_name"])
               for s in rows(os.path.join(d, "stops.txt")) if s["stop_lat"]}
        cand = {i for i, (x, y, _) in pos.items() if window.contains(Point(x, y)) or win2.contains(Point(x, y))}
        deps = defaultdict(list)       # (route_id, dir, stop_id) -> departure seconds on `day`
        last = {}                      # trip_id -> (stop_sequence, stop_id) of its final stop
        with open(os.path.join(d, "stop_times.txt"), newline="", encoding="utf-8-sig") as f:
            rd = csv.DictReader(f)
            for r in rd:
                tid = r["trip_id"]
                if tid in trip_ids:
                    stop_routes[r["stop_id"]].add(wanted[trip_route[tid]])
                    if tid in trip_info:
                        seq = int(r["stop_sequence"])
                        if seq > last.get(tid, (-1, ""))[0]:
                            last[tid] = (seq, r["stop_id"])
                        if r["stop_id"] in cand:
                            ri, di, _ = trip_info[tid]
                            deps[(ri, di, r["stop_id"])].append(secs(r["departure_time"] or r["arrival_time"]))
        # reference stop per route+direction: prefer stops at/near the NC, then most trips
        by_rd = defaultdict(list)
        for (ri, di, sid), v in deps.items():
            x, y, _ = pos[sid]
            by_rd[(ri, di)].append((Point(x, y).distance(nc) * 111_320, -len(v), sid, v))
        heads = defaultdict(Counter)
        for tid, (ri, di, h) in trip_info.items():
            # Metro's feed has no headsigns: label the direction by the trip's terminal stop.
            end = pos.get(last.get(tid, (0, ""))[1], (0, 0, ""))[2]
            heads[(ri, di)][h or (f"to {end}" if end else "")] += 1
        for (ri, di), cands in sorted(by_rd.items()):
            rname = REF_STOP_NAME.get(wanted[ri])
            named = [c for c in cands if pos[c[2]][2] == rname] if rname else []
            near = named or [c for c in cands if c[0] <= 80] or [min(cands)]
            dist, negn, sid, v = min(near, key=lambda c: (c[1], c[0]))
            if wanted[ri] in NO_HEADWAY:
                continue
            hw = headways(v)
            hw_rows.append({"route": wanted[ri], "direction": heads[(ri, di)].most_common(1)[0][0] or f"Direction {di}",
                            "stop": pos[sid][2], "dist_to_nc_m": round(dist), "trips": len(v),
                            "first": hhmm(min(v)), "last": hhmm(max(v)), **hw})
        for s in rows(os.path.join(d, "stops.txt")):
            if s["stop_id"] in stop_routes:
                p = (float(s["stop_lon"]), float(s["stop_lat"]))
                cr = sorted(stop_routes[s["stop_id"]]) if mode == "rail" else sorted(stop_routes[s["stop_id"]] & CORRIDOR_ROUTES)
                if cr and win2.contains(Point(p)):
                    corr_stops[(d, s["stop_id"])] = {"id": s["stop_id"], "name": s["stop_name"],
                                                     "lon": round(p[0], 6), "lat": round(p[1], 6),
                                                     "mode": mode, "routes": cr}
                if window.contains(Point(p)):
                    all_stops[(d, s["stop_id"])] = {
                        "id": s["stop_id"], "name": s["stop_name"], "lon": round(p[0], 6), "lat": round(p[1], 6),
                        "mode": mode, "routes": sorted(stop_routes[s["stop_id"]]),
                        "in_nc": nc.contains(Point(p))}

    stops = list(all_stops.values())
    stations = [s for s in stops if s["mode"] == "rail"]
    for st in stations:   # nearest stop of each bus route, for transfer notes
        conn = {}
        for b in (s for s in stops if s["mode"] == "bus"):
            m = meters((st["lon"], st["lat"]), (b["lon"], b["lat"]))
            for r in b["routes"]:
                if r in BUS_COLORS and m <= MAX_WALK_M and m < conn.get(r, {"m": 1e9})["m"]:
                    conn[r] = {"m": round(m), "stop": b["name"], "lon": b["lon"], "lat": b["lat"]}
        st["connections"] = dict(sorted(conn.items()))

    # Transfers: rail stations (by name) with a Bus 2 or Bus 4 stop within TRANSFER_M
    c_stops = list(corr_stops.values())
    stations_c = {}
    for st in c_stops:
        if st["mode"] == "rail":
            cur = stations_c.setdefault(st["name"], dict(st))
            cur["routes"] = sorted(set(cur["routes"]) | set(st["routes"]))
    transfers = []
    for name, st in sorted(stations_c.items()):
        t = {"station": name, "lon": st["lon"], "lat": st["lat"], "lines": st["routes"]}
        for rte in ("2", "4"):
            best = None
            for b in (x for x in c_stops if x["mode"] == "bus" and rte in x["routes"]):
                m = meters((st["lon"], st["lat"]), (b["lon"], b["lat"]))
                if best is None or m < best["m"]:
                    best = {"m": round(m), "stop": b["name"], "lon": b["lon"], "lat": b["lat"]}
            if best and best["m"] <= TRANSFER_M:
                t["bus" + rte] = best
        if "bus2" in t or "bus4" in t:
            transfers.append(t)
    links = [t for t in transfers if "Westlake" in t["station"]]
    corridor = {"view": list(CORRIDOR_VIEW), "lines": corr_lines, "stops": [x for x in c_stops if x["mode"] == "bus"],
                "transfers": transfers,
                "endpoints": [{"name": n, "lon": st["lon"], "lat": st["lat"]} for n, st in stations_c.items() if n.startswith("Union Station")]}

    out = {"generated": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(timespec="seconds"),
           "gtfs_source": "https://gitlab.com/LACMTA/gtfs_bus , https://gitlab.com/LACMTA/gtfs_rail",
           "boundary_note": nc_note,
           "boundary": mapping(nc), "view": list(view), "colors": {**BUS_COLORS, "B": RAIL_COLOR, "D": D_COLOR},
           "lines": lines, "stops": stops, "corridor": corridor,
           "headways": {"date": day.isoformat(), "rows": hw_rows,
                        "windows": WINDOW_TEXT}}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(out, f, separators=(",", ":"))
    for h in hw_rows:
        print(f"  {h['route']:>5} {h['direction'][:22]:22} @{h['stop'][:28]:28} peak={h['peak']} mid={h['midday']} off={h['offpeak']} night={h['overnight']} trips={h['trips']}", file=sys.stderr)
    for t in transfers:
        print(f"  transfer {t['station']} {t['lines']} bus2={t.get('bus2', {}).get('m')} bus4={t.get('bus4', {}).get('m')}", file=sys.stderr)
    print(f"lines={len(lines)} stops={len(stops)} stations={len(stations)} -> {OUT}", file=sys.stderr)
    for st in stations:
        print(f"  B Line: {st['name']}  " + ", ".join(f"{r}:{c['m']}m" for r, c in st["connections"].items()), file=sys.stderr)


if __name__ == "__main__":
    main()
