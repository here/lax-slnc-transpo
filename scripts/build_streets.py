#!/usr/bin/env python3
"""Build site/streets/data/streets.json: just the named streets around Silver Lake NC.

Street geometry: Caltrans "All Roads" layer (public road network incl. state highways),
https://caltrans-gis.dot.ca.gov/arcgis/rest/services/CHhighway/All_Roads
Train stops: B Line stations already extracted by build_transit.py (site/transit/data/transit.json).

Needs: pip install shapely
"""
import json, math, os, sys, urllib.parse, urllib.request

from shapely.geometry import LineString, box

ROOT = os.path.join(os.path.dirname(__file__), "..", "site")
SRC = "https://caltrans-gis.dot.ca.gov/arcgis/rest/services/CHhighway/All_Roads/FeatureServer/0/query"
OUT = os.path.join(ROOT, "streets", "data", "streets.json")

# label -> RouteId LIKE pattern ("%" wildcards). Ramps and frontage roads are excluded below.
STREETS = {
    "Vermont Ave": "%VERMONT AVE%",
    "Sunset Blvd": "%SUNSET BLVD%",
    "Silver Lake Blvd": "%SILVER LAKE BLVD%",
    "Hyperion Ave": "%HYPERION AVE%",
    "Temple St": "%TEMPLE ST%",
    "Glendale Blvd": "%GLENDALE BLVD%",
    "Alvarado St": "%ALVARADO ST%",
    "Rowena Ave": "%ROWENA AVE%",
    "Santa Monica Blvd": "%SANTA MONICA BLVD%",
    "Beverly Blvd": "%BEVERLY BLVD%",
    "Melrose Ave": "%MELROSE AVE%",
    "US-101 (Hollywood Fwy)": "SHS_101._P",
}


def query(pattern, bbox):
    where = (f"RouteId LIKE '{pattern}' AND LRSToDate IS NULL "
             "AND RouteId NOT LIKE '%FRONTAGE%' AND RouteId NOT LIKE 'RAMP%'")
    q = {"where": where, "geometry": ",".join(map(str, bbox)), "geometryType": "esriGeometryEnvelope",
         "inSR": "4326", "outSR": "4326", "spatialRel": "esriSpatialRelIntersects", "outFields": "RouteId",
         "returnGeometry": "true", "maxAllowableOffset": "0.00008", "geometryPrecision": "6", "f": "json"}
    req = urllib.request.Request(SRC + "?" + urllib.parse.urlencode(q), headers={"User-Agent": "slnc-transit-map/1.0"})
    with urllib.request.urlopen(req, timeout=180) as r:
        d = json.load(r)
    if d.get("error"):
        raise RuntimeError(d["error"])
    return d.get("features", [])


# where along each street (0 to 1) its label sits; default is the middle. Keeps labels off the B Line stop labels.
LABEL_AT = {"Vermont Ave": 0.93, "Santa Monica Blvd": 0.8, "Melrose Ave": 0.85}


def midpoint(lines, frac=0.5):
    """Point `frac` of the way along the longest line (by length), for placing the street's label."""
    def seg(a, b):
        return math.hypot((b[0] - a[0]) * math.cos(math.radians(a[1])), b[1] - a[1])
    best = max(lines, key=lambda c: sum(seg(a, b) for a, b in zip(c, c[1:])))
    half = sum(seg(a, b) for a, b in zip(best, best[1:])) * frac
    run = 0
    for a, b in zip(best, best[1:]):
        d = seg(a, b)
        if run + d >= half and d > 0:
            t = (half - run) / d
            return [round(a[0] + (b[0] - a[0]) * t, 5), round(a[1] + (b[1] - a[1]) * t, 5)]
        run += d
    return best[0]


def main():
    transit = json.load(open(os.path.join(ROOT, "transit", "data", "transit.json")))
    view = transit["view"]                       # minx, miny, maxx, maxy
    window = box(*view)
    streets, labels = {}, {}
    for label, pat in STREETS.items():
        lines, seen = [], set()
        for f in query(pat, view):
            for path in f["geometry"]["paths"]:
                if len(path) < 2:
                    continue
                clipped = LineString(path).intersection(window)
                for part in (clipped.geoms if hasattr(clipped, "geoms") else [clipped]):
                    if part.geom_type != "LineString" or part.length == 0:
                        continue
                    coords = [[round(x, 5), round(y, 5)] for x, y in part.simplify(0.00002).coords]
                    key = (tuple(coords[0]), tuple(coords[-1]), len(coords))
                    if key not in seen:
                        seen.add(key)
                        lines.append(coords)
        streets[label] = lines
        if lines:
            labels[label] = midpoint(lines, LABEL_AT.get(label, 0.5))
        print(f"  {label:26} {len(lines)} lines, {sum(len(l) for l in lines)} points", file=sys.stderr)

    stations = {}
    for s in transit["stops"]:
        if s["mode"] == "rail":
            stations.setdefault(s["name"], {"name": s["name"], "lon": s["lon"], "lat": s["lat"], "lines": s["routes"]})
    out = {"view": view, "streets": streets, "labels": labels, "stations": list(stations.values()), "boundary": transit["boundary"],
           "source": "Caltrans All Roads (public road network)"}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(out, f, separators=(",", ":"))
    print(f"-> {OUT} ({os.path.getsize(OUT) // 1024} KB), {len(stations)} train stops", file=sys.stderr)


if __name__ == "__main__":
    main()
