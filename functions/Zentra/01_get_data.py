import json
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
    response = get_readings_response(
        serial_number=serial_number,
        start_date=start_date,
        end_date=end_date,
        token=token,
    )
    response.raise_for_status()

    data = response.json()
    readings_df = pd.DataFrame(**json.loads(data["data"]))

    timestamp = end_dt.strftime("%Y%m%dT%H%M%SZ")
    output_name = f"zentra_{serial_number}_{timestamp}.csv"
    readings_df.to_csv(output_name, index=False)

    faasr_put_file(
        local_file=output_name,
        remote_folder="Zentra",
        remote_file=output_name,
    )
    faasr_log(f"Uploaded Zentra readings to Zentra/{output_name}")
