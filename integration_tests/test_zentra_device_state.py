"""Integration tests for Zentra ``devices.csv`` rotation and invocation resolution."""

from __future__ import annotations

import io
from uuid import uuid4

import pandas as pd
import pytest

from integration_tests.conftest import WorkflowTester

# Generate a unique invocation ID for each test
INVOCATION_ID = str(uuid4())

SERIALS_BASE = ["z6-19594", "z6-12196"]
SERIALS_EXTRA = SERIALS_BASE + ["z6-12202"]
SERIALS_REMOVED = SERIALS_BASE[:1]  # ZentraRemovedSerial.json serial_numbers
FIRST_SERIAL = SERIALS_BASE[0]
SECOND_SERIAL = SERIALS_BASE[1]
THIRD_SERIAL = "z6-12202"

EPOCH_PREFIX = "1970"


@pytest.fixture(scope="module", autouse=True)
def tester(workflow_file):
    def generate_testers():
        with workflow_file(
            "workflows/Zentra.json",
            invocation_id=INVOCATION_ID,
            num_invocations=3,
        ) as rotation:
            yield rotation
        with workflow_file(
            "workflows/ZentraExtraSerial.json",
            invocation_id=INVOCATION_ID,
        ) as extra_serial:
            yield extra_serial
        with workflow_file(
            "workflows/ZentraRemovedSerial.json",
            invocation_id=INVOCATION_ID,
        ) as removed_serial:
            yield removed_serial

    return generate_testers()


@pytest.fixture(scope="module")
def rotation_tester(tester) -> WorkflowTester:
    return next(tester)


def load_devices_csv(tester: WorkflowTester) -> pd.DataFrame:
    content = tester.s3_client.get_object(tester.get_s3_key("devices.csv"))
    return pd.read_csv(io.StringIO(content))


def is_epoch_timestamp(value: object) -> bool:
    return str(value).startswith(EPOCH_PREFIX)


def serials_with_recent_timestamps(df: pd.DataFrame, serials: list[str]) -> list[str]:
    subset = df[df["serial_number"].astype(str).isin(serials)]
    return [
        str(row["serial_number"])
        for _, row in subset.iterrows()
        if not is_epoch_timestamp(row["timestamp"])
    ]


def row_for_serial(df: pd.DataFrame, serial: str) -> pd.Series:
    matches = df[df["serial_number"].astype(str) == serial]
    assert len(matches) == 1, f"Expected one row for {serial!r}, got {len(matches)}"
    return matches.iloc[0]


def test_first_invocation_creates_devices_csv_and_claims_first_serial(
    rotation_tester: WorkflowTester,
):
    rotation_tester.wait_for("GetZentraData", invocation_num=1)
    rotation_tester.assert_function_completed("GetZentraData")
    rotation_tester.assert_object_exists("devices.csv")

    df = load_devices_csv(rotation_tester)
    assert set(df.columns) == {"serial_number", "timestamp", "invocation_id"}
    assert set(df["serial_number"].astype(str)) == set(SERIALS_BASE)

    claimed = df[df["invocation_id"].astype(str) == INVOCATION_ID]
    assert len(claimed) == 1
    assert str(claimed.iloc[0]["serial_number"]) == FIRST_SERIAL

    second_row = row_for_serial(df, SECOND_SERIAL)
    assert second_row["invocation_id"] == "" or pd.isna(second_row["invocation_id"])
    assert is_epoch_timestamp(second_row["timestamp"])

    rotation_tester.assert_logs_contain(
        "GetZentraData", f"Created devices.csv; claimed {FIRST_SERIAL}"
    )
    rotation_tester.assert_logs_contain(
        "GetZentraData", f"Selected device serial {FIRST_SERIAL}"
    )


def test_append_resolves_claimed_serial(rotation_tester: WorkflowTester):
    rotation_tester.wait_for("AppendZentraData", invocation_num=1)
    rotation_tester.assert_function_completed("AppendZentraData")


def test_second_invocation_rotates_to_second_serial(rotation_tester: WorkflowTester):
    rotation_tester.wait_for("GetZentraData", invocation_num=2)
    rotation_tester.assert_function_completed("GetZentraData")

    df = load_devices_csv(rotation_tester)
    assert set(serials_with_recent_timestamps(df, SERIALS_BASE)) == set(SERIALS_BASE)

    claimed = df[df["invocation_id"].astype(str) == INVOCATION_ID]
    assert len(claimed) == 2
    assert set(claimed["serial_number"].astype(str)) == set(SERIALS_BASE)

    rotation_tester.assert_logs_contain(
        "GetZentraData", f"Updated devices.csv; claimed {SECOND_SERIAL}"
    )


def test_third_invocation_rotates_back_to_first_serial(rotation_tester: WorkflowTester):
    rotation_tester.wait_for("GetZentraData", invocation_num=3)
    rotation_tester.assert_function_completed("GetZentraData")

    df = load_devices_csv(rotation_tester)
    assert set(serials_with_recent_timestamps(df, SERIALS_BASE)) == set(SERIALS_BASE)

    claimed = df[df["invocation_id"].astype(str) == INVOCATION_ID]
    assert len(claimed) == 2
    assert set(claimed["serial_number"].astype(str)) == set(SERIALS_BASE)

    rotation_tester.assert_logs_contain(
        "GetZentraData", f"Updated devices.csv; claimed {FIRST_SERIAL}"
    )


def test_new_serial_claimed_before_rotation(tester):
    extra_tester = next(tester)
    extra_tester.wait_for("GetZentraData")
    extra_tester.assert_function_completed("GetZentraData")

    df = load_devices_csv(extra_tester)
    assert THIRD_SERIAL in df["serial_number"].astype(str).values
    assert set(df["serial_number"].astype(str)) == set(SERIALS_EXTRA)

    third_row = row_for_serial(df, THIRD_SERIAL)
    assert str(third_row["invocation_id"]) == INVOCATION_ID
    assert not is_epoch_timestamp(third_row["timestamp"])

    extra_tester.assert_logs_contain(
        "GetZentraData", f"Updated devices.csv; claimed {THIRD_SERIAL}"
    )


def test_untracked_serials_preserved_when_removed_from_workflow(tester):
    removed_tester = next(tester)
    removed_tester.wait_for("GetZentraData")
    removed_tester.assert_function_completed("GetZentraData")

    df = load_devices_csv(removed_tester)
    assert set(df["serial_number"].astype(str)) == set(SERIALS_EXTRA)
    assert set(SERIALS_REMOVED) == {FIRST_SERIAL}

    first_row = row_for_serial(df, FIRST_SERIAL)
    assert str(first_row["invocation_id"]) == INVOCATION_ID
    assert not is_epoch_timestamp(first_row["timestamp"])

    for serial in (SECOND_SERIAL, THIRD_SERIAL):
        row = row_for_serial(df, serial)
        assert not is_epoch_timestamp(row["timestamp"])

    removed_tester.assert_logs_contain(
        "GetZentraData", f"Updated devices.csv; claimed {FIRST_SERIAL}"
    )
