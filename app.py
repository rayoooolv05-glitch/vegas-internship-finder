"""Streamlit dashboard for Construction Management internships in Southern Nevada."""

import os
from datetime import date

import streamlit as st

from fetcher import DEFAULT_QUERIES, Job, get_searches_left, load_or_fetch
from listing import SORT_OPTIONS, matches_filters, snippet, sort_jobs
from tracking import (
    details_for,
    export_csv,
    has_tracked,
    load_tracking,
    merge_tracking,
    set_flag,
    tracking_from_upload,
    tracking_to_json,
)

PAGE_SIZE = 20
RESTORE_KEY = "restore_file"

st.set_page_config(page_title="Las Vegas Construction Internships", layout="wide")


def resolve_api_key() -> str | None:
    """Read the key from the environment first, then from .streamlit/secrets.toml."""
    key = os.environ.get("SERPAPI_API_KEY")
    if key:
        return key
    try:
        return st.secrets["SERPAPI_API_KEY"]
    except Exception:
        return None


@st.cache_data(show_spinner="Loading internships...")
def get_results(api_key: str, force: bool) -> tuple[list[Job], str, str]:
    return load_or_fetch(api_key, force=force)


@st.cache_data(ttl=60 * 60, show_spinner=False)
def get_quota(api_key: str) -> int | None:
    return get_searches_left(api_key)


def save_flag(job: Job, flag: str, key: str) -> None:
    if not set_flag(job.job_id, flag, st.session_state[key], details_for(job)):
        st.session_state["notice"] = "Could not save Saved/Applied changes to data/tracking.json."


def restore_backup() -> None:
    upload = st.session_state.get(RESTORE_KEY)
    if upload is None:
        st.session_state["notice"] = "Choose a .csv or .json backup file first."
        return
    try:
        incoming = tracking_from_upload(upload.name, upload.getvalue())
    except ValueError as error:
        st.session_state["notice"] = f"Could not restore {upload.name}: {error}."
        return
    if merge_tracking(incoming):
        st.session_state["notice"] = f"Restored {len(incoming)} listings from {upload.name}."
    else:
        st.session_state["notice"] = "Could not write data/tracking.json, so nothing was restored."


def show_more() -> None:
    st.session_state["show_count"] = st.session_state.get("show_count", PAGE_SIZE) + PAGE_SIZE


def deadline_text(job: Job) -> str:
    if job.deadline_date is None:
        return "Not listed"
    text = job.deadline_date.strftime("%b %d, %Y")
    return f"{text} (passed)" if job.deadline_date < date.today() else text


def render_card(job: Job, state: dict) -> None:
    with st.container(border=True):
        details, actions = st.columns([4, 1])
        with details:
            st.markdown(f"#### {job.title}")
            st.markdown(f"**{job.company}** · {job.location or 'Location not listed'}")
            badges = []
            if job.top_contractor:
                badges.append("⭐ Top Contractor")
            if job.summer_2027:
                badges.append("☀️ Summer 2027")
            if badges:
                st.markdown(" · ".join(badges))
            st.markdown(f"**Pay:** {job.pay or 'Pay not listed'}")
            st.markdown(
                f"**Deadline:** {deadline_text(job)}  \n"
                f"**Posted:** {job.posted_at or 'Check listing'}"
            )
            st.write(snippet(job.description))
        with actions:
            if job.apply_link:
                st.link_button("Apply ↗", job.apply_link)
            else:
                st.caption("No apply link listed")
            for flag, label in (("saved", "Saved"), ("applied", "Applied")):
                key = f"{flag}_{job.job_id}"
                st.toggle(
                    label,
                    value=state.get(flag, False),
                    key=key,
                    on_change=save_flag,
                    args=(job, flag, key),
                )


def main() -> None:
    st.title("Construction Management Internships")
    st.caption("Las Vegas and Southern Nevada job sites · Google Jobs via SerpApi")

    api_key = resolve_api_key()
    if not api_key:
        st.error(
            "No SerpApi key found. Set SERPAPI_API_KEY in your environment or in "
            ".streamlit/secrets.toml, then restart the app."
        )
        st.stop()

    tracking = load_tracking()
    any_applied = any(entry.get("applied") for entry in tracking.values())

    with st.sidebar:
        st.header("Filters")
        titles = st.multiselect("Job title", options=DEFAULT_QUERIES, default=DEFAULT_QUERIES)
        keyword = st.text_input("Keyword in company, title, or description")
        sort_by = st.selectbox("Sort by", SORT_OPTIONS)
        # Starts on when applied listings exist; after that, your own choice is kept.
        hide_applied = st.checkbox("Hide applied", value=any_applied)
        st.divider()
        refresh = st.button(
            "Refresh results", help=f"Runs {len(DEFAULT_QUERIES)} SerpApi searches."
        )
        if refresh:
            get_results.clear()
            get_quota.clear()

    jobs, fetched_at, message = get_results(api_key, refresh)
    if refresh or message:
        st.session_state["notice"] = message

    with st.sidebar:
        quota = get_quota(api_key)
        st.caption(f"SerpApi searches left this month: {quota if quota is not None else 'unknown'}")
        st.caption(f"A refresh uses {len(DEFAULT_QUERIES)} searches. Page loads never search.")
        st.divider()
        st.subheader("Backup and restore")
        st.caption(
            "Saved and Applied are stored on the server. Download a backup before a "
            "redeploy, then restore it afterwards."
        )
        st.download_button(
            "Download saved & applied CSV",
            data=export_csv(tracking, jobs),
            file_name="las_vegas_internships_tracked.csv",
            mime="text/csv",
            disabled=not has_tracked(tracking),
        )
        st.download_button(
            "Download backup (JSON)",
            data=tracking_to_json(tracking),
            file_name="tracking_backup.json",
            mime="application/json",
            disabled=not tracking,
        )
        st.file_uploader("Restore from a CSV or JSON backup", type=["csv", "json"], key=RESTORE_KEY)
        st.button("Restore saved & applied", on_click=restore_backup)

    notice = st.session_state.get("notice", "")
    if notice:
        st.warning(notice)
    st.caption(f"Last SerpApi refresh: {fetched_at or 'never (click Refresh results)'}")

    visible = sort_jobs(
        [job for job in jobs if matches_filters(job, titles, keyword, tracking, hide_applied)],
        sort_by,
    )
    saved_count = sum(tracking.get(job.job_id, {}).get("saved", False) for job in jobs)
    applied_count = sum(tracking.get(job.job_id, {}).get("applied", False) for job in jobs)
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Matching internships", len(visible))
    col2.metric("Companies", len({job.company for job in visible}))
    col3.metric("Saved", saved_count)
    col4.metric("Applied", applied_count)

    if not jobs:
        st.info("No internships saved yet. Click Refresh results to search Las Vegas.")
        return
    if not visible:
        st.info("No internships match these filters.")
        return

    shown = visible[: st.session_state.get("show_count", PAGE_SIZE)]
    for job in shown:
        render_card(job, tracking.get(job.job_id, {}))

    remaining = len(visible) - len(shown)
    if remaining > 0:
        st.button(f"Show {min(PAGE_SIZE, remaining)} more", on_click=show_more)


main()
