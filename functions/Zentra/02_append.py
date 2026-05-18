import pandas as pd
from FaaSr_py.client.py_client_stubs import (
    faasr_get_file,
    faasr_get_folder_list,
    faasr_invocation_id,
    faasr_log,
    faasr_put_file,
)
from zentra_devices_state import remote_path, resolve_serial_for_invocation


def _get_timestamp_column(df: pd.DataFrame) -> str:
    candidates = ("timestamp", "Timestamp", "date_time", "datetime", "time", "DateTime")
    for col in candidates:
        if col in df.columns:
            return col
    raise ValueError(
        "Could not find timestamp column in CSV. Expected one of: "
        + ", ".join(candidates)
    )


def _complete_file_exists(folder: str, remote_complete: str) -> bool:
    objects = faasr_get_folder_list(prefix=remote_complete)
    return any(
        obj == remote_complete or obj.endswith(f"/{remote_complete}")
        for obj in objects
    )


def append_zentra_segment(folder: str):
    """
    Merge the latest segment CSV into the serial-specific complete CSV.

    Resolves ``serial_number`` from ``devices.csv`` using the current
    ``faasr_invocation_id()`` (must match the row updated by ``download_zentra_readings``).
    """
    invocation_id = faasr_invocation_id()
    faasr_log(f"Using invocation ID: {invocation_id}")

    serial_number = resolve_serial_for_invocation(invocation_id, folder)
    segment_local = "latest.csv"
    complete_name = f"{serial_number}_complete.csv"
    remote_latest = remote_path(invocation_id, f"{serial_number}_segments/latest.csv")
    remote_complete = remote_path(invocation_id, complete_name)

    # 1) Download latest segment created by previous function.
    faasr_get_file(
        local_file=segment_local,
        remote_folder=folder,
        remote_file=remote_latest,
    )
    segment_df = pd.read_csv(segment_local)

    if segment_df.empty:
        faasr_log("Latest segment file is empty; nothing to append")
        return

    ts_col = _get_timestamp_column(segment_df)
    segment_df[ts_col] = pd.to_datetime(segment_df[ts_col], errors="coerce", utc=True)
    segment_df = segment_df.dropna(subset=[ts_col]).sort_values(ts_col)

    if segment_df.empty:
        faasr_log("No valid timestamps found in latest segment; nothing to append")
        return

    # 2) Check if complete file exists before downloading it.
    if _complete_file_exists(folder, remote_complete):
        faasr_get_file(
            local_file=complete_name,
            remote_folder=folder,
            remote_file=remote_complete,
        )
        complete_df = pd.read_csv(complete_name)
        if complete_df.empty:
            merged_df = segment_df.copy()
        else:
            complete_ts_col = _get_timestamp_column(complete_df)
            complete_df[complete_ts_col] = pd.to_datetime(
                complete_df[complete_ts_col], errors="coerce", utc=True
            )
            complete_df = complete_df.dropna(subset=[complete_ts_col]).sort_values(
                complete_ts_col
            )

            if complete_df.empty:
                merged_df = segment_df.copy()
            else:
                latest_ts = complete_df[complete_ts_col].max()
                new_rows = segment_df[segment_df[ts_col] > latest_ts]
                merged_df = pd.concat([complete_df, new_rows], ignore_index=True)
                faasr_log(
                    f"Existing complete file found. Appended {len(new_rows)} new rows."
                )
    else:
        merged_df = segment_df.copy()
        faasr_log("No existing complete file found. Creating a new complete CSV.")

    merged_df.to_csv(complete_name, index=False)
    faasr_put_file(
        local_file=complete_name,
        remote_folder=folder,
        remote_file=remote_complete,
    )
    faasr_log(f"Uploaded complete file: {remote_complete}")
