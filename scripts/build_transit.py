#!/usr/bin/env python3
"""Build site/transit/data/transit.json: transit lines through Silver Lake NC.

Inputs (downloaded here, never committed):
  * LA Metro GTFS bus + rail feeds (gitlab.com/LACMTA/gtfs_bus, gtfs_rail)
  * 311 case coordinates tagged "SILVER LAKE NC" (data.lacity.org)

The NC outline is APPROXIMATE: a concave hull of those 311 coordinates, because no
official boundary polygon was reachable. Replace `boundary` with the official
GeoJSON when available (LA GeoHub "Neighborhood Councils (Certified)").

Needs: pip install shapely
"""
import csv, io, json, math, os, sys, tempfile, urllib.parse, urllib.request, zipfile
from collections import Counter, defaultdict

from shapely import concave_hull
from shapely.geometry import LineString, MultiPoint, Point, mapping
from shapely.ops import unary_union

BUS_ROUTES = {"2": "2-13201", "4": "4-13201", "10": "10-13201", "92": "92-13201", "93": "93-13201", "182": "182-13201"}
DASH_ROUTES = {"DASH": "4869"}   # LADOT DASH Pico Union/Echo Park (not in the Metro feed)
BUS_COLORS = {"2": "#d95f02", "4": "#1b9e77", "10": "#7570b3", "92": "#e7298a", "93": "#a6761d", "182": "#66a61e", "DASH": "#e6ab02"}
RAIL_ROUTE, RAIL_COLOR = "802", "#eb131b"  # B Line
GITLAB = "https://gitlab.com/LACMTA/{}/-/raw/master/{}"
LADOT_GTFS = "https://ladotbus.com/gtfs"   # LADOT DASH feed; see their GTFS developer license
OUT = os.path.join(os.path.dirname(__file__), "..", "site", "transit", "data", "transit.json")
MARGIN_DEG = 0.010        # ~1 km of context around the NC outline (shows the Echo Park DASH)
MAX_WALK_M = 1000         # list nearest stop of each route within this walk of a B Line station


def fetch(url, dest):
    with urllib.request.urlopen(url, timeout=300) as r, open(dest, "wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)


def rows(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        yield from csv.DictReader(f)


def meters(a, b):
    dy = (a[1] - b[1]) * 111_320
    dx = (a[0] - b[0]) * 111_320 * math.cos(math.radians(a[1]))
    return math.hypot(dx, dy)


def boundary():
    q = urllib.parse.urlencode({
        "$select": "geolocation__latitude__s as lat,geolocation__longitude__s as lon,count(*)",
        "$where": "locator_sr_neigborhood_council_1='SILVER LAKE NC' AND geolocation__latitude__s IS NOT NULL",
        "$group": "lat,lon", "$limit": "50000"})
    with urllib.request.urlopen("https://data.lacity.org/resource/2cy6-i7zn.json?" + q, timeout=120) as r:
        pts = [(float(p["lon"]), float(p["lat"])) for p in json.load(r)]
    # West edge per the council: 101 Freeway (south), Hoover St, Fountain Ave, Hyperion (north).
    # Pin the Hoover corners so the hull reaches Fountain and the 101 exactly there.
    pts += [(-118.2847, 34.0958),   # Hoover & Fountain
            (-118.2845, 34.0768)]   # Hoover & 101 Freeway
    hull = concave_hull(MultiPoint(pts), ratio=0.3).buffer(0.0004).simplify(0.0001)
    if hull.geom_type != "Polygon":  # keep the biggest piece
        hull = max(hull.geoms, key=lambda g: g.area)
    return hull, len(pts)


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
    for f in ("routes", "trips", "shapes", "stops", "stop_times"):
        fetch(GITLAB.format("gtfs_rail", f + ".txt"), os.path.join(rail, f + ".txt"))

    nc, npts = boundary()
    minx, miny, maxx, maxy = nc.bounds
    view = (minx - MARGIN_DEG, miny - MARGIN_DEG, maxx + MARGIN_DEG, maxy + MARGIN_DEG)
    # B Line runs under Vermont Ave, west of the NC: widen the window to include it.
    view = (min(view[0], -118.2935), view[1], view[2], view[3])
    from shapely.geometry import box
    window = box(*view)

    lines, all_stops = [], {}
    feeds = [(bus, dict((rid, k) for k, rid in BUS_ROUTES.items()), "bus"),
             (dash, dict((rid, k) for k, rid in DASH_ROUTES.items()), "bus"),
             (rail, {RAIL_ROUTE: "B"}, "rail")]
    for d, wanted, mode in feeds:
        trips = defaultdict(Counter)   # route_id -> (shape_id, dir) -> n
        trip_route = {}
        for t in rows(os.path.join(d, "trips.txt")):
            if t["route_id"] in wanted:
                trips[t["route_id"]][(t["shape_id"], t.get("direction_id", ""))] += 1
                trip_route[t["trip_id"]] = t["route_id"]
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
        seen = set()
        for rid, sids in keep.items():
            label = wanted[rid]
            for sid in sorted(sids):
                ls = LineString([(x, y) for _, x, y in sorted(shp[sid])])
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
        with open(os.path.join(d, "stop_times.txt"), newline="", encoding="utf-8-sig") as f:
            rd = csv.DictReader(f)
            for r in rd:
                if r["trip_id"] in trip_ids:
                    stop_routes[r["stop_id"]].add(wanted[trip_route[r["trip_id"]]])
        for s in rows(os.path.join(d, "stops.txt")):
            if s["stop_id"] in stop_routes:
                p = (float(s["stop_lon"]), float(s["stop_lat"]))
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

    out = {"generated": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(timespec="seconds"),
           "gtfs_source": "https://gitlab.com/LACMTA/gtfs_bus , https://gitlab.com/LACMTA/gtfs_rail",
           "boundary_note": f"Approximate outline: concave hull of {npts} unique 311 case locations tagged SILVER LAKE NC. Not the official boundary.",
           "boundary": mapping(nc), "view": list(view), "colors": {**BUS_COLORS, "B": RAIL_COLOR},
           "lines": lines, "stops": stops}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(out, f, separators=(",", ":"))
    print(f"lines={len(lines)} stops={len(stops)} stations={len(stations)} -> {OUT}", file=sys.stderr)
    for st in stations:
        print(f"  B Line: {st['name']}  " + ", ".join(f"{r}:{c['m']}m" for r, c in st["connections"].items()), file=sys.stderr)


if __name__ == "__main__":
    main()
