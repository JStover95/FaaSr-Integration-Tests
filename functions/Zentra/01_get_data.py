import json
import random
import time
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests
from FaaSr_py.client.py_client_stubs import (
    faasr_get_file,
    faasr_get_folder_list,
    faasr_log,
    faasr_put_file,
    faasr_secret,
)


def get_with_credentials(token: str, uri: str, **kwargs) -> requests.Response:
    """Perform a GET request with Zentra token authorization."""
    auth_header = token if token.lower().startswith("token") else f"Token {token}"
    headers = {"Authorization": auth_header}
    return requests.get(uri, headers=headers, timeout=20, **kwargs)


def get_readings_response(
    serial_number: str,
    start_date: str,
    end_date: str,
    token: str,
    server: str = "https://zentracloud.com",
) -> requests.Response:
    """Request readings from the Zentra API."""
    url = f"{server}/api/v4/get_readings/"
    params = {
        "output_format": "df",
        "per_page": 100,
        "page_num": 1,
        "sort_by": "desc",
        "start_date": start_date,
        "end_date": end_date,
        "device_sn": serial_number,
    }
    return get_with_credentials(token, url, params=params)


def get_readings_with_backoff(
    serial_number: str,
    start_date: str,
    end_date: str,
    token: str,
    total_timeout_seconds: int = 120,
) -> requests.Response:
    """Request Zentra readings with exponential backoff, jittered waits, and a total timeout.

    After each failure, wait time is ``X + U(0, X)`` seconds (``U`` uniform), where ``X`` is
    the current backoff base (1, 2, 4, … capped at 16), then capped by remaining budget.
    """
    start_time = time.monotonic()
    delay_seconds = 1
    max_delay_seconds = 16
    attempt = 1
    last_error: Exception | None = None

    while True:
        elapsed = time.monotonic() - start_time
        if elapsed >= total_timeout_seconds:
            raise TimeoutError(
                f"Failed to fetch Zentra readings within {total_timeout_seconds} seconds"
            ) from last_error

        try:
            response = get_readings_response(
                serial_number=serial_number,
                start_date=start_date,
                end_date=end_date,
                token=token,
            )
            response.raise_for_status()
            if attempt > 1:
                faasr_log(f"Zentra request succeeded on attempt {attempt}")
            return response
        except requests.RequestException as exc:
            last_error = exc
            elapsed = time.monotonic() - start_time
            remaining = total_timeout_seconds - elapsed
            if remaining <= 0:
                break

            base_delay = delay_seconds
            jittered = base_delay + random.uniform(0, base_delay)
            sleep_seconds = min(jittered, remaining)
            faasr_log(
                f"Zentra request attempt {attempt} failed: {exc}. "
                f"Retrying in {sleep_seconds:.1f}s "
                f"(base {base_delay}s + jitter up to {base_delay}s, capped by {remaining:.1f}s left)"
            )
            time.sleep(sleep_seconds)
            delay_seconds = min(delay_seconds * 2, max_delay_seconds)
            attempt += 1

    raise TimeoutError(
        f"Failed to fetch Zentra readings within {total_timeout_seconds} seconds"
    ) from last_error


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


def _latest_timestamp_utc(complete_name: str, serial_number: str) -> datetime | None:
    """Download complete CSV and return max timestamp as timezone-aware UTC, or None."""
    local_complete = f"_get_data_{serial_number}_complete.csv"
    faasr_get_file(
        local_file=local_complete,
        remote_folder="",
        remote_file=complete_name,
    )
    df = pd.read_csv(local_complete)
    if df.empty:
        return None
    ts_col = _get_timestamp_column(df)
    ts = pd.to_datetime(df[ts_col], errors="coerce", utc=True)
    ts = ts.dropna()
    if ts.empty:
        return None
    last = ts.max()
    if isinstance(last, pd.Timestamp):
        return last.to_pydatetime()
    return pd.Timestamp(last).to_pydatetime()


def _compute_lookback_timedelta(
    end_dt: datetime, min_hours: int, last_ts: datetime | None
) -> timedelta:
    """
    Decide how far back to query the Zentra API.

    - No prior complete file / no usable last row: ``min_hours``.
    - If age from last row to now is at most ``min_hours``: still ``min_hours`` (minimum window).
    - If age exceeds ``min_hours``: ``age + 1 hour`` (buffer against gaps).
    """
    min_td = timedelta(hours=int(min_hours))
    if last_ts is None:
        faasr_log(f"No usable last timestamp; using minimum lookback {min_hours}h")
        return min_td

    if last_ts.tzinfo is None:
        last_ts = last_ts.replace(tzinfo=timezone.utc)
    age = end_dt - last_ts
    if age < timedelta(0):
        faasr_log("Last timestamp is after current time; using minimum lookback")
        return min_td

    if age <= min_td:
        faasr_log(
            f"Last row age {age} <= min_hours ({min_hours}h); using minimum lookback"
        )
        return min_td

    lookback = age + timedelta(hours=1)
    faasr_log(
        f"Last row age {age} > min_hours ({min_hours}h); "
        f"using lookback {lookback} (age + 1h buffer)"
    )
    return lookback


def download_zentra_readings(serial_number: str, min_hours: int):
    """
    Download Zentra readings using a minimum lookback and optional incremental window.

    ``min_hours`` is always the minimum API window. If ``<serial>_complete.csv`` exists
    and its latest row is older than ``min_hours``, the window expands to
    (now - last_timestamp) plus one hour.
    """
    faasr_log("Retrieving Zentra token from secret store")
    token = faasr_secret("ZENTRA_TOKEN")

    end_dt = datetime.now(timezone.utc)
    complete_name = f"{serial_number}_complete.csv"
    last_ts: datetime | None = None

    if _complete_file_exists(complete_name):
        try:
            last_ts = _latest_timestamp_utc(complete_name, serial_number)
        except Exception as exc:
            faasr_log(
                f"Could not read last timestamp from {complete_name}: {exc}. "
                f"Falling back to min_hours={min_hours}"
            )
            last_ts = None
    else:
        faasr_log(
            f"No complete file {complete_name}; using minimum lookback {min_hours}h"
        )

    lookback = _compute_lookback_timedelta(end_dt, int(min_hours), last_ts)
    start_dt = end_dt - lookback
    end_date = end_dt.strftime("%Y-%m-%d %H:%M:%S")
    start_date = start_dt.strftime("%Y-%m-%d %H:%M:%S")

    faasr_log(
        f"Requesting Zentra readings for {serial_number} from {start_date} to {end_date} (UTC)"
    )
    response = get_readings_with_backoff(
        serial_number=serial_number,
        start_date=start_date,
        end_date=end_date,
        token=token,
    )

    data = response.json()
    readings_df = pd.DataFrame(**json.loads(data["data"]))

    timestamp = end_dt.strftime("%Y%m%dT%H%M%SZ")
    output_name = f"zentra_{serial_number}_{timestamp}.csv"
    segments_folder = f"{serial_number}_segments"
    readings_df.to_csv(output_name, index=False)

    faasr_put_file(
        local_file=output_name,
        remote_folder=segments_folder,
        remote_file=output_name,
    )
    # Upload a stable pointer file for downstream append step.
    faasr_put_file(
        local_file=output_name,
        remote_folder=segments_folder,
        remote_file="latest.csv",
    )

    faasr_log(f"Uploaded Zentra readings to {segments_folder}/{output_name}")


def no_op():
    """No-op function to allow for multiple GetZentraData actions."""
    faasr_log("No-op function called")
    return
