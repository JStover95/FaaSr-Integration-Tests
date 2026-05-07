import pandas as pd
from FaaSr_py.client.py_client_stubs import faasr_get_file, faasr_log, faasr_put_file


def _get_timestamp_column(df: pd.DataFrame) -> str:
    candidates = ("timestamp", "Timestamp", "date_time", "datetime", "time", "DateTime")
    for col in candidates:
        if col in df.columns:
            return col
    raise ValueError(
        "Could not find timestamp column in CSV. Expected one of: "
        + ", ".join(candidates)
    )


def append_zentra_segment(serial_number: str):
    """
    Merge the latest segment CSV into the serial-specific complete CSV.
    """
    segments_folder = f"{serial_number}_segments"
    segment_local = "latest.csv"
    complete_name = f"{serial_number}_complete.csv"

    # 1) Download latest segment created by previous function.
    faasr_get_file(
        local_file=segment_local,
        remote_folder=segments_folder,
        remote_file="latest.csv",
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

    # 2) Try downloading the complete file. If it does not exist, create it from segment.
    try:
        faasr_get_file(
            local_file=complete_name,
            remote_folder="",
            remote_file=complete_name,
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
    except Exception:
        merged_df = segment_df.copy()
        faasr_log("No existing complete file found. Creating a new complete CSV.")

    merged_df.to_csv(complete_name, index=False)
    faasr_put_file(
        local_file=complete_name,
        remote_folder="",
        remote_file=complete_name,
    )
    faasr_log(f"Uploaded complete file: {complete_name}")
