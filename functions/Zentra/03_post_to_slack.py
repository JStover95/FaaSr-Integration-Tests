import json

import pandas as pd
import requests
from FaaSr_py.client.py_client_stubs import (
    faasr_get_file,
    faasr_get_folder_list,
    faasr_invocation_id,
    faasr_log,
    faasr_secret,
)

from .zentra_devices_state import resolve_serial_for_invocation


def _get_timestamp_column(df: pd.DataFrame) -> str:
    candidates = ("timestamp", "Timestamp", "date_time", "datetime", "time", "DateTime")
    for col in candidates:
        if col in df.columns:
            return col
    raise ValueError(
        "Could not find timestamp column in CSV. Expected one of: "
        + ", ".join(candidates)
    )


def _complete_file_exists(complete_name: str) -> bool:
    objects = faasr_get_folder_list(prefix=complete_name)
    return any(
        obj == complete_name or obj.endswith(f"/{complete_name}") for obj in objects
    )


def _format_ts_range(ts_series: pd.Series) -> tuple[str, str]:
    """Return (start_str, end_str) in UTC ISO-like format for display."""
    if ts_series.empty:
        return ("n/a", "n/a")
    mn = ts_series.min()
    mx = ts_series.max()
    return (str(mn), str(mx))


def post_zentra_summary_to_slack(slack_channel: str):
    """
    Download latest segment and complete CSVs, summarize, post to Slack.

    Resolves ``serial_number`` from ``devices.csv`` using ``faasr_invocation_id()``.

    Credentials: ``faasr_secret("SLACK_WEBHOOK_URL")`` — Incoming Webhook URL.
    Optional ``slack_channel`` (e.g. ``#alerts``) is sent in the webhook payload
    when non-empty so the message can target a channel the app can post to.

    Args:
        slack_channel: Slack channel name or ID (e.g. ``#zentra``). Empty string
            omits ``channel`` from the payload (webhook default channel is used).
    """
    serial_number = resolve_serial_for_invocation(faasr_invocation_id())
    segments_folder = f"{serial_number}_segments"
    latest_local = "slack_latest.csv"
    complete_name = f"{serial_number}_complete.csv"
    complete_local = "slack_complete.csv"

    faasr_get_file(
        local_file=latest_local,
        remote_folder=segments_folder,
        remote_file="latest.csv",
    )
    latest_df = pd.read_csv(latest_local)
    latest_rows = len(latest_df)

    if latest_df.empty or latest_rows == 0:
        start_s, end_s = "n/a", "n/a"
    else:
        ts_col = _get_timestamp_column(latest_df)
        ts = pd.to_datetime(latest_df[ts_col], errors="coerce", utc=True)
        ts = ts.dropna()
        if ts.empty:
            start_s, end_s = "n/a", "n/a"
        else:
            start_s, end_s = _format_ts_range(ts)

    if _complete_file_exists(complete_name):
        faasr_get_file(
            local_file=complete_local,
            remote_folder="",
            remote_file=complete_name,
        )
        complete_df = pd.read_csv(complete_local)
        complete_rows = len(complete_df)
    else:
        complete_rows = 0
        faasr_log(f"Complete file not found: {complete_name}; reporting 0 rows")

    text = (
        f"*Zentra ingest* — `{serial_number}`\n"
        f"• *Latest pull:* {latest_rows} rows"
        f" (start {start_s} → end {end_s} UTC)\n"
        f"• *Complete file:* {complete_rows} rows total (`{complete_name}`)"
    )

    faasr_log("Posting summary to Slack via incoming webhook")
    webhook_url = faasr_secret("SLACK_WEBHOOK_URL")
    payload: dict = {"text": text}
    if slack_channel and slack_channel.strip():
        payload["channel"] = slack_channel.strip()

    response = requests.post(
        webhook_url,
        data=json.dumps(payload),
        headers={"Content-Type": "application/json"},
        timeout=20,
    )
    response.raise_for_status()
    faasr_log("Slack webhook request succeeded")
