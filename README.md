# Las Vegas Construction Internship Finder

A Streamlit dashboard that pulls internship listings for Construction Management
students in Las Vegas, NV from Google Jobs via [SerpApi](https://serpapi.com).

Searched titles: Project Engineer Intern, Estimating Intern, Construction Intern.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export SERPAPI_API_KEY=your_key_here   # free key at serpapi.com
```

## Run

```bash
streamlit run app.py
```

Results are cached in `data/jobs_cache.json` for 24 hours to conserve the free
SerpApi monthly allowance. Use **Refresh results** in the sidebar to force a new fetch.

## Test

```bash
pytest
```

## Layout

- `fetcher.py`: SerpApi client, normalization to `Job` records, and disk cache
- `app.py`: Streamlit dashboard with sidebar title filters
- `tests/`: unit tests for normalization (no network calls)
