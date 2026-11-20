# lax-slnc-transpo
Last-month MyLA311 requests for the Silver Lake Neighborhood Council, published via GitHub Pages.
- `scripts/fetch.py` pulls from data.lacity.org (dataset `2cy6-i7zn`) into `site/data/cases.json`; refreshed daily by `.github/workflows/pages.yml`.
- Optional secret `SOCRATA_APP_TOKEN` (repo Settings → Secrets → Actions). Never commit it.
- `@claude` mentions in issues/PRs run `.github/workflows/claude.yml` (needs secret `ANTHROPIC_API_KEY`).
