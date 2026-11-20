#!/usr/bin/env python3
"""Fetch the last N days of MyLA311 cases for Silver Lake NC into site/data/cases.json.

Dataset: MyLA311 Cases 2026 (data.lacity.org, id 2cy6-i7zn).
Optional env var SOCRATA_APP_TOKEN raises rate limits (never commit it).
"""
import json, os, sys, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone

DATASET = os.environ.get("SOCRATA_DATASET", "2cy6-i7zn")
NC = "SILVER LAKE NC"
DAYS = int(os.environ.get("DAYS", "31"))
OUT = os.path.join(os.path.dirname(__file__), "..", "site", "data", "cases.json")

since = (datetime.now(timezone.utc) - timedelta(days=DAYS)).strftime("%Y-%m-%dT00:00:00")
params = {
    "$select": ("casenumber,createddate,type,status,origin,closeddate,department_name__c,"
                "locator_gis_returned_address,geolocation__latitude__s,geolocation__longitude__s"),
    "$where": f"locator_sr_neigborhood_council_1 = '{NC}' AND createddate >= '{since}'",
    "$order": "createddate DESC",
    "$limit": "50000",
}
headers = {"Accept": "application/json"}
if os.environ.get("SOCRATA_APP_TOKEN"):
    headers["X-App-Token"] = os.environ["SOCRATA_APP_TOKEN"]

url = f"https://data.lacity.org/resource/{DATASET}.json?" + urllib.parse.urlencode(params)
def get(h):
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=120) as r:
        return json.load(r)

try:
    rows = get(headers)
except urllib.error.HTTPError as e:
    if e.code in (401, 403) and "X-App-Token" in headers:
        print("app token rejected; retrying without it", file=sys.stderr)
        rows = get({"Accept": "application/json"})
    else:
        raise

def num(v):
    try: return round(float(v), 6)
    except (TypeError, ValueError): return None

cases = [{
    "id": r["casenumber"], "created": r["createddate"], "type": r.get("type"),
    "status": r.get("status"), "origin": r.get("origin"), "closed": r.get("closeddate"),
    "dept": r.get("department_name__c"), "address": r.get("locator_gis_returned_address"),
    "lat": num(r.get("geolocation__latitude__s")), "lon": num(r.get("geolocation__longitude__s")),
} for r in rows]

out = {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
       "neighborhood_council": NC, "since": since, "source": f"https://data.lacity.org/d/{DATASET}",
       "count": len(cases), "cases": cases}
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w") as f:
    json.dump(out, f, separators=(",", ":"))
print(f"wrote {len(cases)} cases since {since}", file=sys.stderr)
