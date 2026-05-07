import json
import time
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests
from FaaSr_py.client.py_client_stubs import faasr_log, faasr_put_file, faasr_secret


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
    """Request Zentra readings with exponential backoff and a total timeout."""
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

            sleep_seconds = min(delay_seconds, remaining)
            faasr_log(
                f"Zentra request attempt {attempt} failed: {exc}. "
                f"Retrying in {sleep_seconds:.1f}s"
            )
            time.sleep(sleep_seconds)
            delay_seconds = min(delay_seconds * 2, max_delay_seconds)
            attempt += 1

    raise TimeoutError(
        f"Failed to fetch Zentra readings within {total_timeout_seconds} seconds"
    ) from last_error


def download_zentra_readings(serial_number: str, num_hours: int):
    """
    Download Zentra readings for the most recent `num_hours` and upload a timestamped CSV to S3.
    """
    faasr_log("Retrieving Zentra token from secret store")
    token = faasr_secret("ZENTRA_TOKEN")

    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(hours=int(num_hours))
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
