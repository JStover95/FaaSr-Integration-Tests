"""Shared S3-backed device rotation state for Zentra workflows (`devices.csv`)."""

from __future__ import annotations

import json

import pandas as pd
from FaaSr_py.client.py_client_stubs import (
    faasr_exit,
    faasr_get_file,
    faasr_get_folder_list,
    faasr_log,
    faasr_put_file,
)

DEVICES_FILE = "devices.csv"
DEVICE_COLUMNS = ["serial_number", "timestamp", "invocation_id"]
EPOCH_UTC = pd.Timestamp("1970-01-01T00:00:00+00:00")


def remote_path(invocation_id: str, file_name: str) -> str:
    """S3 object path under the workflow folder: ``{invocation_id}/{file_name}``."""
    return f"{invocation_id}/{file_name}"


def normalize_serial_numbers(serial_numbers) -> list[str]:
    """Coerce workflow argument to a list of strings (supports JSON array string)."""
    if serial_numbers is None:
        return []
    if isinstance(serial_numbers, str):
        s = serial_numbers.strip()
        if s.startswith("["):
            return [str(x) for x in json.loads(s)]
        return [s] if s else []
    return [str(x) for x in serial_numbers]


def devices_csv_exists(folder: str, invocation_id: str) -> bool:
    remote_file = remote_path(invocation_id, DEVICES_FILE)
    objects = faasr_get_folder_list(prefix=remote_file)
    return any(
        obj == remote_file or obj.endswith(f"/{remote_file}") for obj in objects
    )


def _load_devices(folder: str, invocation_id: str) -> pd.DataFrame:
    remote_file = remote_path(invocation_id, DEVICES_FILE)
    faasr_get_file(
        local_file=DEVICES_FILE,
        remote_folder=folder,
        remote_file=remote_file,
    )
    df = pd.read_csv(DEVICES_FILE)
    for col in DEVICE_COLUMNS:
        if col not in df.columns:
            faasr_exit(
                message=f"{DEVICES_FILE} missing required column {col!r}",
                error=True,
            )
    return df


def _save_devices(folder: str, invocation_id: str, df: pd.DataFrame) -> None:
    remote_file = remote_path(invocation_id, DEVICES_FILE)
    out = df[DEVICE_COLUMNS].copy()
    out.to_csv(DEVICES_FILE, index=False)
    faasr_put_file(
        local_file=DEVICES_FILE,
        remote_folder=folder,
        remote_file=remote_file,
    )


def _ts_to_iso(ts) -> str:
    if pd.isna(ts):
        return EPOCH_UTC.isoformat()
    return pd.Timestamp(ts).isoformat()


def select_and_claim_serial(
    serial_numbers, invocation_id: str, folder: str
) -> str:
    """
    Pick the device serial for this run and persist claim on ``devices.csv``.

    - If ``devices.csv`` is missing: create one row per entry in ``serial_numbers``,
      set epoch timestamps, then set the **first** serial's ``timestamp`` and
      ``invocation_id`` to now / this invocation.
    - If it exists: keep rows whose serial is **not** in ``serial_numbers`` unchanged
      (ignored for scheduling). For tracked serials, append any missing from the array
      (epoch slots). If any serials were **newly** added, claim the **first** new serial
      (array order). Otherwise claim the tracked serial with the **earliest** timestamp,
      then set its ``timestamp`` and ``invocation_id`` to now / this invocation.
    """
    serial_numbers = normalize_serial_numbers(serial_numbers)
    if not serial_numbers:
        faasr_exit(message="serial_numbers must be a non-empty list", error=True)

    inv = str(invocation_id)
    now = pd.Timestamp.now(tz="UTC")

    if not devices_csv_exists(folder, inv):
        df = pd.DataFrame(
            [
                {
                    "serial_number": s,
                    "timestamp": EPOCH_UTC.isoformat(),
                    "invocation_id": "",
                }
                for s in serial_numbers
            ]
        )
        first = serial_numbers[0]
        df.loc[df["serial_number"].astype(str) == first, "timestamp"] = now.isoformat()
        df.loc[df["serial_number"].astype(str) == first, "invocation_id"] = inv
        _save_devices(folder, inv, df)
        faasr_log(
            f"Created {DEVICES_FILE}; claimed {first} for invocation {inv}"
        )
        return first

    df = _load_devices(folder, inv)
    df["serial_number"] = df["serial_number"].astype(str)
    in_set = set(serial_numbers)
    mask_tracked = df["serial_number"].isin(in_set)
    tracked = df.loc[mask_tracked, DEVICE_COLUMNS].copy()
    extras = df.loc[~mask_tracked, DEVICE_COLUMNS].copy()

    pre_serials = set(tracked["serial_number"].astype(str))
    newly_added = [s for s in serial_numbers if s not in pre_serials]

    if newly_added:
        new_rows = pd.DataFrame(
            [
                {
                    "serial_number": s,
                    "timestamp": EPOCH_UTC.isoformat(),
                    "invocation_id": "",
                }
                for s in newly_added
            ]
        )
        tracked = pd.concat([tracked, new_rows], ignore_index=True)

    tracked["timestamp"] = pd.to_datetime(
        tracked["timestamp"], utc=True, errors="coerce"
    )
    tracked["timestamp"] = tracked["timestamp"].fillna(EPOCH_UTC)

    if newly_added:
        chosen = newly_added[0]
    else:
        idx = tracked["timestamp"].idxmin()
        chosen = str(tracked.loc[idx, "serial_number"])

    tracked.loc[tracked["serial_number"] == chosen, "timestamp"] = now
    tracked.loc[tracked["serial_number"] == chosen, "invocation_id"] = inv
    tracked["timestamp"] = tracked["timestamp"].map(_ts_to_iso)

    out = pd.concat([tracked, extras], ignore_index=True)
    _save_devices(folder, inv, out)
    faasr_log(f"Updated {DEVICES_FILE}; claimed {chosen} for invocation {inv}")
    return chosen


def resolve_serial_for_invocation(
    invocation_id: str, folder: str
) -> str:
    """Return the serial number claimed for this invocation, or exit with error."""
    inv = str(invocation_id)
    if not devices_csv_exists(folder, inv):
        faasr_exit(
            message=f"{DEVICES_FILE} not found; cannot resolve invocation {inv!r}",
            error=True,
        )
    df = _load_devices(folder, inv)
    match = df.loc[df["invocation_id"].astype(str) == inv, "serial_number"]
    if match.empty:
        faasr_exit(
            message=f"invocation_id {inv!r} not found in {DEVICES_FILE}",
            error=True,
        )
    return str(match.iloc[0])
