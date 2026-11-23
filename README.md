# lax-slnc-transpo
Data supporting the Silver Lake Neighborhood Council, published via GitHub Pages and at https://aviary.herebox.org/slnc/.

Pages: `/` SLNC data (last 30 days of 311 in the top five types, transit map image), `/311/` 311 data, `/transit/` transit and walking connections (`/streets/` is an unlisted lighter transit map). The shared top and bottom menu is `site/nav.js`.

- `scripts/fetch.py` pulls from data.lacity.org (dataset `2cy6-i7zn`) into `site/data/cases.json`; refreshed daily by `.github/workflows/pages.yml`.
- Optional secret `SOCRATA_APP_TOKEN` (repo Settings → Secrets → Actions). Never commit it.
- `scripts/build_transit.py` (needs `shapely`) rebuilds `site/transit/data/transit.json` from LA Metro and LADOT GTFS; run by hand.
- `scripts/build_streets.py` (needs `shapely`) rebuilds `site/streets/data/streets.json` from the Caltrans All Roads layer; run it after `build_transit.py`.
