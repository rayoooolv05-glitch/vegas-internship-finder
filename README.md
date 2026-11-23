# Las Vegas Construction Internship Finder

A Streamlit dashboard for Construction Management students looking for internships in
Las Vegas and Southern Nevada (Henderson, North Las Vegas, Summerlin, Paradise, Spring Valley,
Boulder City). Listings come from Google Jobs through [SerpApi](https://serpapi.com).

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Provide your SerpApi key in one of these ways:

- Environment variable: `export SERPAPI_API_KEY=your_key_here`
- Streamlit secrets: create `.streamlit/secrets.toml` containing `SERPAPI_API_KEY = "your_key_here"`

Neither location is committed to git.

## Run

```bash
streamlit run app.py
```

## How searches and the free quota work

- A **Refresh results** click runs one SerpApi search per role in `DEFAULT_QUERIES`
  (16 at present), so each refresh uses 16 of the 250 monthly searches.
- Page loads, filter changes, sorting, and Saved/Applied toggles read the saved results
  in `data/jobs_cache.json` and never call SerpApi.
- The sidebar shows the searches left this month. That check uses SerpApi's account
  endpoint and does not use a search.
- If a refresh fails or finds nothing, the saved results stay on screen with a message.

## Tracking

- **Saved** and **Applied** toggles on each card are stored in `data/tracking.json`.
- **Hide applied** removes applied listings from the list.
- **Download saved & applied CSV** exports the tracked listings that appear in the saved results.

## Test

```bash
pytest
```

Tests do not call the network.

## Layout

- `fetcher.py`: SerpApi client, normalization (pay, posting age, deadlines), and the disk cache
- `listing.py`: filters, sort orders, snippets, and CSV export (no Streamlit)
- `tracking.py`: Saved and Applied flags
- `app.py`: Streamlit dashboard
- `tests/`: unit tests for all of the above
