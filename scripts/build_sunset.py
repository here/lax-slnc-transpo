#!/usr/bin/env python3
"""Build site/sunset/data/sunset.json: Bus 4 on Sunset Blvd / Cesar E Chavez Ave from Douglas St to Union Station,
the five busiest bus lines that cross or join it there, rail lines and stations, light reference streets,
transfer points and weekday headways.

Sources: LA Metro GTFS (bus + rail, gitlab.com/LACMTA), Caltrans All Roads (street geometry).
Needs: pip install shapely. Reuses helpers from build_transit.py.
"""
import csv, json, os, re, sys, tempfile, urllib.parse, urllib.request, zipfile
from collections import Counter, defaultdict

from shapely.geometry import LineString, MultiLineString, Point, box
from shapely.ops import linemerge, substring, unary_union

sys.path.insert(0, os.path.dirname(__file__))
from build_transit import (GITLAB, active_services, fetch, headways, hhmm, meters, rows, secs,  # noqa: E402
                           service_date)

OUT = os.path.join(os.path.dirname(__file__), "..", "site", "sunset", "data", "sunset.json")
ROADS = "https://caltrans-gis.dot.ca.gov/arcgis/rest/services/CHhighway/All_Roads/FeatureServer/0/query"
VIEW = (-118.2590, 34.0500, -118.2300, 34.0760)    # Douglas St to Union Station; the top edge cuts through Dodger Stadium
CORRIDOR_CLIP = box(-118.2525, 34.0550, -118.2368, 34.0755)   # Sunset from Douglas St, Cesar Chavez to Alameda St
MAIN_ROUTE = "4-13201"
N_CROSSING = 5          # how many crossing lines to show
PINNED = None           # e.g. ["60-13201", ...] to fix the list instead of ranking by weekday trips
RAIL = {"801": "A", "802": "B", "804": "E", "805": "D"}
UNION_STATION = (-118.234249, 34.056197)
DODGER_STADIUM = (-118.2400, 34.0738)   # label position only (stadium outline not drawn)
# Proposed LA ART aerial tram (gondola), drawn from its published route description (Wikipedia, "Route"):
# from Union Station along Alameda St, along the edge of Los Angeles State Historic Park with a station by the
# A Line's Chinatown station, along the A Line tracks to an angle point, up Bishops Rd, across the 110 near
# Stadium Way to the stadium. Station positions and the last stretch are approximate.
COLORS = ["#d95f02", "#1b9e77", "#7570b3", "#e7298a", "#66a61e"]
RAIL_COLORS = {"A": "#0072bc", "B": "#eb131b", "D": "#a05da5", "E": "#fdb913"}
STREETS = {
    "Sunset Blvd": "%SUNSET BLVD%", "Cesar E Chavez Ave": "%CESAR E CHAVEZ AVE%", "Douglas St": "%DOUGLAS ST%",
    "Echo Park Ave": "%ECHO PARK AVE%", "Glendale Blvd": "%GLENDALE BLVD%", "Figueroa St": "%FIGUEROA ST%",
    "Hill St": "%HILL ST%", "Broadway": "%BROADWAY%", "Spring St": "%SPRING ST%", "Main St": "%MAIN ST%",
    "Alameda St": "%ALAMEDA ST%", "Stadium Way": "%STADIUM WAY%", "Elysian Park Ave": "%ELYSIAN PARK AVE%",
    "Temple St": "%TEMPLE ST%", "US-101": "SHS_101._P", "I-110": "SHS_110._P",
}


def roads(pattern, bbox):
    q = {"where": f"RouteId LIKE '{pattern}' AND LRSToDate IS NULL AND RouteId NOT LIKE '%FRONTAGE%' "
                  "AND RouteId NOT LIKE 'RAMP%' AND RouteId NOT LIKE '%SPUR%'",
         "geometry": ",".join(map(str, bbox)), "geometryType": "esriGeometryEnvelope", "inSR": "4326", "outSR": "4326",
         "spatialRel": "esriSpatialRelIntersects", "outFields": "RouteId", "returnGeometry": "true",
         "maxAllowableOffset": "0.00004", "geometryPrecision": "6", "f": "json"}
    req = urllib.request.Request(ROADS + "?" + urllib.parse.urlencode(q), headers={"User-Agent": "slnc-transit-map/1.0"})
    with urllib.request.urlopen(req, timeout=180) as r:
        d = json.load(r)
    if d.get("error"):
        raise RuntimeError(d["error"])
    return [p for f in d.get("features", []) for p in f["geometry"]["paths"] if len(p) > 1]


def parts(geom):
    for g in (geom.geoms if hasattr(geom, "geoms") else [geom]):
        if g.geom_type == "LineString" and g.length > 0:
            yield g


def label_point(lines):
    best = max(lines, key=lambda c: LineString(c).length)
    p = LineString(best).interpolate(0.5, normalized=True)
    return [round(p.x, 5), round(p.y, 5)]


def main():
    window = box(*VIEW)
    tmp = tempfile.mkdtemp(prefix="gtfs_")
    bus, rail = os.path.join(tmp, "bus"), os.path.join(tmp, "rail")
    os.makedirs(bus); os.makedirs(rail)
    print("downloading GTFS…", file=sys.stderr)
    fetch(GITLAB.format("gtfs_bus", "gtfs_bus.zip"), os.path.join(tmp, "bus.zip"))
    zipfile.ZipFile(os.path.join(tmp, "bus.zip")).extractall(bus)
    for f in ("routes", "trips", "shapes", "stops", "stop_times", "calendar", "calendar_dates"):
        fetch(GITLAB.format("gtfs_rail", f + ".txt"), os.path.join(rail, f + ".txt"))

    # streets (reference layer) and the corridor itself
    streets, labels = {}, {}
    for name, pat in STREETS.items():
        lines = []
        for path in roads(pat, VIEW):
            for g in parts(LineString(path).intersection(window)):
                lines.append([[round(x, 5), round(y, 5)] for x, y in g.simplify(0.00002).coords])
        if lines:
            streets[name], labels[name] = lines, label_point(lines)
    corr = linemerge(unary_union([MultiLineString(roads("%SUNSET BLVD%", VIEW)),
                                  MultiLineString(roads("%CESAR E CHAVEZ AVE%", VIEW))]).intersection(CORRIDOR_CLIP))
    near_corr = corr.buffer(0.0003)          # ~30 m: "on the corridor"
    mid = corr.interpolate(0.5, normalized=True) if corr.geom_type == "LineString" else corr.centroid

    day = service_date((bus, rail))
    print(f"headways measured on {day}", file=sys.stderr)
    out_lines, stations, hw_rows, transfers = [], {}, [], []
    # ---- bus feed: rank crossing lines, then collect shapes, stops and departures
    on = active_services(bus, day)
    rname = {r["route_id"]: (r["route_short_name"], r["route_desc"]) for r in rows(os.path.join(bus, "routes.txt"))}
    ntrips, shapes, trip_info = Counter(), defaultdict(Counter), {}
    for t in rows(os.path.join(bus, "trips.txt")):
        if t["service_id"] in on:
            ntrips[t["route_id"]] += 1
            shapes[t["route_id"]][(t["shape_id"], t.get("direction_id", ""))] += 1
            trip_info[t["trip_id"]] = (t["route_id"], t.get("direction_id", ""))
    top_shapes = {rid: [s for (s, _), _ in c.most_common(4)] for rid, c in shapes.items()}
    want = {s for v in top_shapes.values() for s in v}
    pts = defaultdict(list)
    for r in rows(os.path.join(bus, "shapes.txt")):
        if r["shape_id"] in want:
            pts[r["shape_id"]].append((int(r["shape_pt_sequence"]), float(r["shape_pt_lon"]), float(r["shape_pt_lat"])))
    geom = {s: LineString([(x, y) for _, x, y in sorted(v)]) for s, v in pts.items() if len(v) > 1}
    touching = []
    for rid, sids in top_shapes.items():
        if rid != MAIN_ROUTE and any(s in geom and geom[s].intersects(near_corr) for s in sids):
            touching.append(rid)
    ranked = sorted(touching, key=lambda r: -ntrips[r])
    chosen = PINNED or ranked[:N_CROSSING]
    keep = [MAIN_ROUTE] + chosen
    label = {rid: rname[rid][0] for rid in keep}
    colors = {"4": "#1b1b1b", **{label[r]: COLORS[i] for i, r in enumerate(chosen)}, **RAIL_COLORS}

    for rid in keep:
        seen = set()
        for (sid, _), _ in shapes[rid].most_common(6):
            if sid not in geom:
                continue
            for g in parts(geom[sid].intersection(window)):
                key = tuple(round(c, 4) for c in (g.coords[0] + g.coords[-1]))
                if key in seen or tuple(reversed(key)) in seen:
                    continue
                seen.add(key)
                out_lines.append({"route": label[rid], "mode": "bus",
                                  "coords": [[round(x, 5), round(y, 5)] for x, y in g.simplify(0.00002).coords]})

    pos = {s["stop_id"]: (float(s["stop_lon"]), float(s["stop_lat"]), s["stop_name"])
           for s in rows(os.path.join(bus, "stops.txt")) if s["stop_lat"]}
    in_win = {i for i, (x, y, _) in pos.items() if window.contains(Point(x, y))}
    deps, last = defaultdict(list), {}
    stop_routes = defaultdict(set)
    with open(os.path.join(bus, "stop_times.txt"), newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            ti = trip_info.get(r["trip_id"])
            if not ti or ti[0] not in keep:
                continue
            seq = int(r["stop_sequence"])
            if seq > last.get(r["trip_id"], (-1, ""))[0]:
                last[r["trip_id"]] = (seq, r["stop_id"])
            if r["stop_id"] in in_win:
                deps[(ti[0], ti[1], r["stop_id"])].append(secs(r["departure_time"] or r["arrival_time"]))
                stop_routes[r["stop_id"]].add(ti[0])
    terminal = defaultdict(Counter)
    for tid, (ri, di) in trip_info.items():
        if ri in keep and tid in last:
            terminal[(ri, di)][pos.get(last[tid][1], (0, 0, ""))[2]] += 1

    main_stops = [s for s, rs in stop_routes.items() if MAIN_ROUTE in rs and near_corr.buffer(0.0003).contains(Point(pos[s][:2]))]
    # transfer point per crossing line: its stop closest to a Bus 4 stop on the corridor
    anchor = {MAIN_ROUTE: (mid.x, mid.y)}
    for i, rid in enumerate(chosen):
        best = None
        for s in (s for s, rs in stop_routes.items() if rid in rs):
            for m in main_stops:
                d = meters(pos[s][:2], pos[m][:2])
                if best is None or d < best[0]:
                    best = (d, s, m)
        if best:
            d, s, m = best
            anchor[rid] = pos[s][:2]
            transfers.append({"route": label[rid], "color": COLORS[i], "desc": re.sub(r"\bLa\b", "LA", rname[rid][1].title()), "trips": ntrips[rid],
                              "stop": pos[s][2], "lon": pos[s][0], "lat": pos[s][1],
                              "bus4_stop": pos[m][2], "bus4_lon": pos[m][0], "bus4_lat": pos[m][1], "m": round(d)})
    # headways at the stop nearest each line's transfer point (Bus 4: nearest the corridor's middle)
    by_rd = defaultdict(list)
    for (ri, di, sid), v in deps.items():
        by_rd[(ri, di)].append((meters(pos[sid][:2], anchor.get(ri, (mid.x, mid.y))), -len(v), sid, v))
    for (ri, di), cands in sorted(by_rd.items(), key=lambda kv: keep.index(kv[0][0])):
        d, _, sid, v = min(cands)
        hw_rows.append({"route": label[ri], "direction": "to " + terminal[(ri, di)].most_common(1)[0][0],
                        "stop": pos[sid][2], "trips": len(v), "first": hhmm(min(v)), "last": hhmm(max(v)), **headways(v)})

    # ---- rail: lines (B and D trimmed at Union Station) and stations in the window
    ron = active_services(rail, day)
    rshapes, rtrips = defaultdict(Counter), {}
    for t in rows(os.path.join(rail, "trips.txt")):
        if t["route_id"] in RAIL and t["service_id"] in ron:
            rshapes[t["route_id"]][t["shape_id"]] += 1
            rtrips[t["trip_id"]] = RAIL[t["route_id"]]
    rwant = {s for c in rshapes.values() for s, _ in c.most_common(4)}
    rpts = defaultdict(list)
    for r in rows(os.path.join(rail, "shapes.txt")):
        if r["shape_id"] in rwant:
            rpts[r["shape_id"]].append((int(r["shape_pt_sequence"]), float(r["shape_pt_lon"]), float(r["shape_pt_lat"])))
    for rid, c in rshapes.items():
        lab, seen = RAIL[rid], set()
        for sid, _ in c.most_common(4):
            ls = LineString([(x, y) for _, x, y in sorted(rpts[sid])])
            if lab in ("B", "D") and ls.distance(Point(UNION_STATION)) < 0.0008:
                cut = ls.project(Point(UNION_STATION))
                halves = [h for h in (substring(ls, 0, cut), substring(ls, cut, ls.length)) if h.geom_type == "LineString" and h.length > 0]
                ls = min(halves, key=lambda h: h.bounds[2])
            for g in parts(ls.intersection(window)):
                key = tuple(round(v, 4) for v in (g.coords[0] + g.coords[-1]))
                if key in seen or tuple(reversed(key)) in seen:
                    continue
                seen.add(key)
                out_lines.append({"route": lab, "mode": "rail",
                                  "coords": [[round(x, 5), round(y, 5)] for x, y in g.simplify(0.00002).coords]})
    rpos = {s["stop_id"]: (float(s["stop_lon"]), float(s["stop_lat"]), s["stop_name"]) for s in rows(os.path.join(rail, "stops.txt")) if s["stop_lat"]}
    with open(os.path.join(rail, "stop_times.txt"), newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            lab = rtrips.get(r["trip_id"])
            if lab and r["stop_id"] in rpos and window.contains(Point(rpos[r["stop_id"]][:2])):
                x, y, n = rpos[r["stop_id"]]
                n = n.split(" - ")[0]
                n = n if n == "Union Station" else n.removesuffix(" Station")
                st = stations.setdefault(n, {"name": n, "lon": x, "lat": y, "lines": set()})
                st["lines"].add(lab)
    for st in stations.values():
        st["lines"] = sorted(st["lines"])

    # ---- proposed tram
    tram = None
    try:
        from shapely.geometry import MultiPoint
        def merged(pat):
            g = linemerge(MultiLineString(roads(pat, VIEW)))
            return g if g.geom_type == "LineString" else max(g.geoms, key=lambda x: x.length)
        def piece(line, a, b):
            da, db = line.project(a), line.project(b)
            seg = substring(line, min(da, db), max(da, db))
            cs = list(seg.coords)
            return cs if da <= db else cs[::-1]
        alameda, bishops = merged("LA_LA_N ALAMEDA ST_P"), merged("%BISHOPS RD%")
        a_shape = rshapes["801"].most_common(1)[0][0]
        aline = LineString([(x, y) for _, x, y in sorted(rpts[a_shape])])
        china = next(Point(v[:2]) for v in rpos.values() if v[2] == "Chinatown Station")
        us_pt = alameda.interpolate(alameda.project(Point(UNION_STATION)))
        park_pt = alameda.interpolate(alameda.project(china))
        b_ends = [Point(bishops.coords[0]), Point(bishops.coords[-1])]
        b_east, b_west = sorted(b_ends, key=lambda p: aline.distance(p))
        angle_pt = aline.interpolate(aline.project(b_east))
        cross = merged("LA_LA_STADIUM WAY_P").intersection(merged("SHS_110._P"))
        cross = cross if cross.geom_type == "Point" else (cross.centroid if not cross.is_empty else None)
        coords = piece(alameda, us_pt, park_pt) + piece(aline, aline.interpolate(aline.project(park_pt)), angle_pt) \
            + piece(bishops, b_east, b_west) + ([cross.coords[0]] if cross else []) + [DODGER_STADIUM]
        tram = {"name": "LA ART aerial tram (proposed)",
                "coords": [[round(x, 5), round(y, 5)] for x, y in LineString(coords).simplify(0.00002).coords],
                "stations": [{"name": "Union Station (Alameda St)", "lon": round(us_pt.x, 5), "lat": round(us_pt.y, 5)},
                             {"name": "Chinatown / State Park", "lon": round(park_pt.x, 5), "lat": round(park_pt.y, 5)},
                             {"name": "Dodger Stadium", "lon": DODGER_STADIUM[0], "lat": DODGER_STADIUM[1]}],
                "approx_from": [round(b_west.x, 5), round(b_west.y, 5)]}
        print(f"tram: {len(tram['coords'])} points, {round(LineString(coords).length * 1e5)} m; 110 crossing {cross}", file=sys.stderr)
    except Exception as e:   # the tram is an extra; never fail the build over it
        print(f"tram not built: {e!r}", file=sys.stderr)

    out = {"generated": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(timespec="seconds"),
           "view": list(VIEW), "date": day.isoformat(), "colors": colors,
           "corridor": [[round(x, 5), round(y, 5)] for g in parts(corr) for x, y in g.coords],
           "streets": streets, "labels": labels, "lines": out_lines,
           "bus4_stops": [{"name": pos[s][2], "lon": pos[s][0], "lat": pos[s][1]} for s in main_stops],
           "stations": list(stations.values()), "transfers": transfers, "headways": hw_rows,
           "chosen": [label[r] for r in chosen],
           "runners_up": [{"route": rname[r][0], "trips": ntrips[r]} for r in ranked[N_CROSSING:N_CROSSING + 5]],
           "tram": tram,
           "stadium": {"name": "Dodger Stadium", "lon": DODGER_STADIUM[0], "lat": DODGER_STADIUM[1]},
           "windows": {"peak": "6-9 AM and 3-7 PM", "midday": "9 AM-3 PM", "offpeak": "before 6 AM and after 7 PM"}}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(out, f, separators=(",", ":"))
    print(f"chosen {out['chosen']} (by weekday trips); runners-up {out['runners_up']}", file=sys.stderr)
    for t in transfers:
        print(f"  {t['route']:>4}: {t['stop']} <-> Bus 4 {t['bus4_stop']} ({t['m']} m)", file=sys.stderr)
    for h in hw_rows:
        print(f"  {h['route']:>4} {h['direction'][:28]:28} @{h['stop'][:26]:26} peak={h['peak']} mid={h['midday']} off={h['offpeak']}", file=sys.stderr)
    print(f"streets {list(streets)}; stations {[(s['name'], s['lines']) for s in stations.values()]}; "
          f"lines {len(out_lines)}; bus4 stops {len(main_stops)} -> {OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
