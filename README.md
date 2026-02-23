# UK Polling Wikipedia Tracker (Starter)

This project builds a simple website that:

- fetches the Wikipedia page for UK next general election opinion polling
- stores the latest polling table as JSON
- downloads the polling graph image shown on the page
- displays both on a small website

The website is static (`site/`) so you can host it on GitHub Pages. Python is used only for the daily scraping/update job.

## Project layout

- `scraper.py` - fetches/parses Wikipedia, saves JSON + graph image
- `site/index.html` - frontend page
- `site/app.js` - renders graph + table from `site/data/latest.json`
- `site/styles.css` - styling
- `.github/workflows/update-polling-data.yml` - daily scheduled data refresh
- `.github/workflows/deploy-pages.yml` - deploys `site/` to GitHub Pages

## Local setup

1. Create and activate a virtual environment (optional but recommended)
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run the scraper:

```bash
python scraper.py
```

4. Preview the site locally:

```bash
python -m http.server 8000
```

Then open `http://localhost:8000/site/`.

## GitHub setup (your repo)

1. Create a GitHub repo and push this folder to it.
2. Make sure the default branch is `main` (or update the workflow branch in `.github/workflows/deploy-pages.yml`).
3. In GitHub repo settings:
   - go to **Pages**
   - set source to **GitHub Actions**
4. Run the workflows once manually from the **Actions** tab:
   - `Update UK Polling Data`
   - `Deploy Site to GitHub Pages`

After that:
- data updates daily (06:15 UTC)
- GitHub Pages serves the site from `site/`

## Notes / limitations

- Wikipedia page structure can change, so the graph/table selectors may need occasional updates.
- The scraper auto-detects the table and graph image using heuristics.
- If the graph image cannot be downloaded, the site still shows the table.

## Optional customization

- Change page URL with env var:

```bash
WIKI_PAGE_URL="https://en.wikipedia.org/wiki/Opinion_polling_for_the_next_United_Kingdom_general_election" python scraper.py
```

