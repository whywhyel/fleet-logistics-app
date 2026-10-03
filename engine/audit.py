from datetime import datetime

import pandas as pd


SHIFT_PERIODS = [
    "Morning Report (12:00 PM)",
    "Evening Report (08:00 PM)",
]

HANDOVER_STATUSES = [
    "Pending Review",
    "Complete - Ready for Handover",
    "Escalated Issues Present",
]


def build_shift_metadata(
    shift_period: str,
    operator_name: str,
    handover_status: str,
    shift_notes: str,
    signed_off: bool,
) -> dict:
    """Build a report-level shift audit record."""
    return {
        "Shift_Period": shift_period,
        "Operative": operator_name,
        "Handover_Status": handover_status,
        "Shift_Notes": shift_notes.strip(),
        "Signed_Off": bool(signed_off),
        "Timestamp": datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S WAT"
        ),
    }


def append_audit_trail_to_export(
    df_report: pd.DataFrame,
    shift_metadata: dict,
) -> pd.DataFrame:
    """Stamp the final operational report with shift metadata."""
    result = df_report.copy()

    result["Report_Shift_Period"] = shift_metadata["Shift_Period"]
    result["Processed_By_Operative"] = shift_metadata["Operative"]
    result["Handover_Status"] = shift_metadata["Handover_Status"]
    result["Operative_Handover_Notes"] = shift_metadata["Shift_Notes"]
    result["Shift_SignOff_Timestamp"] = shift_metadata["Timestamp"]
    result["Shift_Signed_Off"] = shift_metadata["Signed_Off"]

    return result
