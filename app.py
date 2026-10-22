"""Streamlit dashboard for Construction Management internships in Las Vegas."""

import pandas as pd
import streamlit as st

from fetcher import DEFAULT_QUERIES, get_api_key, load_or_fetch

st.set_page_config(page_title="Las Vegas Construction Internships", layout="wide")


@st.cache_data(show_spinner="Fetching internships from Google Jobs...", ttl=60 * 60)
def get_jobs_frame(api_key: str, force: bool) -> pd.DataFrame:
    jobs = load_or_fetch(api_key, force=force)
    return pd.DataFrame([job.__dict__ for job in jobs])


def main() -> None:
    st.title("Construction Management Internships: Las Vegas, NV")

    api_key = get_api_key()
    if not api_key:
        st.error("Set the SERPAPI_API_KEY environment variable, then restart the app.")
        st.stop()

    with st.sidebar:
        st.header("Filters")
        selected_titles = st.multiselect(
            "Job title",
            options=DEFAULT_QUERIES,
            default=DEFAULT_QUERIES,
        )
        keyword = st.text_input("Keyword in company or description")
        refresh = st.button("Refresh results")

    if refresh:
        get_jobs_frame.clear()
    df = get_jobs_frame(api_key, force=refresh)

    if df.empty:
        st.info("No internships found right now. Try refreshing later.")
        return

    filtered = df[df["query"].isin(selected_titles)] if selected_titles else df.iloc[0:0]
    if keyword:
        needle = keyword.lower()
        mask = (
            filtered["company"].str.lower().str.contains(needle, regex=False)
            | filtered["description"].str.lower().str.contains(needle, regex=False)
        )
        filtered = filtered[mask]

    col1, col2 = st.columns(2)
    col1.metric("Matching internships", len(filtered))
    col2.metric("Companies", filtered["company"].nunique())

    st.dataframe(
        filtered[["company", "title", "location", "description", "apply_link"]],
        column_config={
            "company": "Company",
            "title": "Job title",
            "location": "Location",
            "description": "Description",
            "apply_link": st.column_config.LinkColumn("Apply", display_text="Apply"),
        },
        hide_index=True,
        use_container_width=True,
    )


if __name__ == "__main__":
    main()
