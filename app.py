"""Streamlit dashboard for Construction Management internships in Las Vegas."""

import pandas as pd
import streamlit as st

from fetcher import (
    DEFAULT_QUERIES,
    get_api_key,
    is_top_contractor,
    load_or_fetch,
    mentions_summer_2027,
)

st.set_page_config(page_title="Las Vegas Construction Internships", layout="wide")


@st.cache_data(show_spinner="Fetching internships from Google Jobs...", ttl=60 * 60)
def get_jobs_frame(api_key: str, force: bool) -> pd.DataFrame:
    jobs = load_or_fetch(api_key, force=force)
    df = pd.DataFrame([job.__dict__ for job in jobs])
    if df.empty:
        return df
    df["top_contractor"] = df["company"].map(is_top_contractor)
    df["summer_2027"] = [
        mentions_summer_2027(title, description)
        for title, description in zip(df["title"], df["description"])
    ]
    df["tags"] = [
        " · ".join(
            label
            for label, flag in (
                ("⭐ Top Contractor", top),
                ("☀️ Summer 2027", summer),
            )
            if flag
        )
        for top, summer in zip(df["top_contractor"], df["summer_2027"])
    ]
    return df


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
        las_vegas_only = st.checkbox("Las Vegas only", value=True)
        keyword = st.text_input("Keyword in company or description")
        refresh = st.button("Refresh results")

    if refresh:
        get_jobs_frame.clear()
    df = get_jobs_frame(api_key, force=refresh)

    if df.empty:
        st.info("No internships found right now. Try refreshing later.")
        return

    filtered = df[df["query"].isin(selected_titles)] if selected_titles else df.iloc[0:0]
    if las_vegas_only:
        filtered = filtered[filtered["location"].str.contains("Las Vegas", case=False, regex=False)]
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
        filtered[["company", "title", "tags", "location", "description", "apply_link"]],
        column_config={
            "company": "Company",
            "title": "Job title",
            "tags": st.column_config.TextColumn("Tags", width="medium"),
            "location": "Location",
            "description": "Description",
            "apply_link": st.column_config.LinkColumn("Apply", display_text="Apply"),
        },
        hide_index=True,
        use_container_width=True,
    )


if __name__ == "__main__":
    main()
