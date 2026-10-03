from io import BytesIO

import pandas as pd
import streamlit as st

from engine.audit import (
    HANDOVER_STATUSES,
    SHIFT_PERIODS,
    append_audit_trail_to_export,
    build_shift_metadata,
)
from engine.data_ingestion import FleetDataIngestor
from engine.geocoding import get_locationiq_key, reverse_geocode_dataframe
from engine.rules_engine import (
    TERMINAL_GEOFENCES,
    FleetRulesEngine,
)
from engine.safety import process_and_merge_safety_alerts


st.set_page_config(
    page_title="GreenTag Fleet Logistics",
    page_icon="🚛",
    layout="wide",
)

st.title("🚛 GreenTag Fleet Logistics")
st.caption(
    "Oil & gas fleet in-transit and logistics automation."
)

st.info(
    "Operational pipeline: VTS + previous report + safety alerts → "
    "normalization → LocationIQ → state transitions → anomaly/geofence "
    "checks → shift audit → signed report."
)


def prepare_operational_dataset(
    report_df: pd.DataFrame,
    vts_df: pd.DataFrame | None,
) -> pd.DataFrame:
    """Merge the previous report with the latest VTS position data."""
    result = report_df.copy()

    if vts_df is None or vts_df.empty or "reg_number" not in vts_df.columns:
        return result

    vts = vts_df.copy()

    rename_map = {}
    if "lat" in vts.columns:
        rename_map["lat"] = "curr_lat"
    if "lon" in vts.columns:
        rename_map["lon"] = "curr_lon"
    if "curr_state" in vts.columns:
        rename_map["curr_state"] = "vts_curr_state"

    vts = vts.rename(columns=rename_map)

    vts_columns = [
        column
        for column in [
            "reg_number",
            "curr_lat",
            "curr_lon",
            "vts_curr_state",
        ]
        if column in vts.columns
    ]

    vts = vts[vts_columns].drop_duplicates(
        subset=["reg_number"],
        keep="last",
    )

    result = result.merge(
        vts,
        on="reg_number",
        how="left",
        suffixes=("", "_vts"),
    )

    if "curr_state" not in result.columns:
        result["curr_state"] = ""

    if "vts_curr_state" in result.columns:
        result["curr_state"] = result["curr_state"].fillna(
            result["vts_curr_state"]
        )
        result.loc[
            result["curr_state"].astype(str).str.strip() == "",
            "curr_state",
        ] = result.loc[
            result["curr_state"].astype(str).str.strip() == "",
            "vts_curr_state",
        ]

    result = result.drop(
        columns=["vts_curr_state"],
        errors="ignore",
    )

    return result


def add_previous_coordinates(df: pd.DataFrame) -> pd.DataFrame:
    """Map source lat/lon to previous coordinates when explicitly available."""
    result = df.copy()

    if "prev_lat" not in result.columns and "lat" in result.columns:
        result["prev_lat"] = pd.to_numeric(
            result["lat"],
            errors="coerce",
        )

    if "prev_lon" not in result.columns and "lon" in result.columns:
        result["prev_lon"] = pd.to_numeric(
            result["lon"],
            errors="coerce",
        )

    return result


def build_excel_export(df: pd.DataFrame) -> bytes:
    """Create an Excel workbook in memory for operational download."""
    output = BytesIO()

    with pd.ExcelWriter(
        output,
        engine="openpyxl",
    ) as writer:
        df.to_excel(
            writer,
            index=False,
            sheet_name="In-Transit Report",
        )

    return output.getvalue()


# ---------------------------------------------------------------------------
# Sidebar: data ingestion
# ---------------------------------------------------------------------------

st.sidebar.header("1. Data Ingestion")

vts_file = st.sidebar.file_uploader(
    "VTS Export",
    type=["csv", "xlsx", "xls"],
    key="vts_upload",
)

previous_report = st.sidebar.file_uploader(
    "Previous Evening Report",
    type=["csv", "xlsx", "xls"],
    key="previous_report_upload",
)

alerts_file = st.sidebar.file_uploader(
    "Driver Behavior Alerts",
    type=["csv", "xlsx", "xls"],
    key="alerts_upload",
)

vts_df = None
report_df = None
alerts_df = None

if vts_file is not None:
    try:
        vts_df = FleetDataIngestor.process_vts_export(vts_file)
        st.sidebar.success(
            f"VTS loaded: {len(vts_df):,} vehicle records."
        )
    except Exception as exc:
        st.sidebar.error(f"VTS processing failed: {exc}")

if previous_report is not None:
    try:
        report_df = FleetDataIngestor.process_previous_report(
            previous_report
        )
        st.sidebar.success(
            f"Previous report loaded: {len(report_df):,} active records."
        )
    except Exception as exc:
        st.sidebar.error(f"Previous report processing failed: {exc}")

if alerts_file is not None:
    try:
        alerts_df = FleetDataIngestor.load_file(alerts_file)
        st.sidebar.success(
            f"Safety alerts loaded: {len(alerts_df):,} events."
        )
    except Exception as exc:
        st.sidebar.error(f"Safety alert processing failed: {exc}")


# ---------------------------------------------------------------------------
# Sidebar: LocationIQ and geofence configuration
# ---------------------------------------------------------------------------

st.sidebar.header("2. Location & Geofence")

locationiq_configured = bool(get_locationiq_key())

geofences = {
    name: values.copy()
    for name, values in TERMINAL_GEOFENCES.items()
}

for terminal_name, fence in geofences.items():
    fence["radius_km"] = st.sidebar.number_input(
        f"{terminal_name} radius (km)",
        min_value=0.1,
        max_value=10.0,
        value=float(fence["radius_km"]),
        step=0.1,
        key=f"radius_{terminal_name}",
    )

use_locationiq = st.sidebar.checkbox(
    "Enable LocationIQ reverse geocoding",
    value=locationiq_configured,
    disabled=not locationiq_configured,
)

if not locationiq_configured:
    st.sidebar.caption(
        "Add LOCATIONIQ_KEY to .streamlit/secrets.toml to enable geocoding."
    )


# ---------------------------------------------------------------------------
# Sidebar: Shift handover
# ---------------------------------------------------------------------------

st.sidebar.header("3. Shift Handover & Sign-Off")

operator_name = st.sidebar.text_input(
    "Active Duty Operative",
    placeholder="Enter operative name",
)

shift_period = st.sidebar.selectbox(
    "Shift Period",
    SHIFT_PERIODS,
)

handover_status = st.sidebar.selectbox(
    "Shift Completion Status",
    HANDOVER_STATUSES,
)

shift_notes = st.sidebar.text_area(
    "Handover Notes / Follow-ups",
    placeholder=(
        "Example: Called driver of KND-123XA. "
        "Awaiting discharge due to customer dispute."
    ),
)

sign_off_confirmed = st.sidebar.checkbox(
    "Confirm Shift Sign-Off & Seal Report",
)


# ---------------------------------------------------------------------------
# Main operational pipeline
# ---------------------------------------------------------------------------

st.subheader("Fleet Operations")

if report_df is None:
    st.warning(
        "Upload the Previous Evening Report to start the operational pipeline."
    )
else:
    operational_df = prepare_operational_dataset(
        report_df,
        vts_df,
    )
    operational_df = add_previous_coordinates(operational_df)

    if "curr_lat" not in operational_df.columns:
        operational_df["curr_lat"] = pd.Series(
            index=operational_df.index,
            dtype="float64",
        )

    if "curr_lon" not in operational_df.columns:
        operational_df["curr_lon"] = pd.Series(
            index=operational_df.index,
            dtype="float64",
        )

    # Use the latest VTS position as the current position.
    operational_df["curr_lat"] = pd.to_numeric(
        operational_df["curr_lat"],
        errors="coerce",
    )
    operational_df["curr_lon"] = pd.to_numeric(
        operational_df["curr_lon"],
        errors="coerce",
    )

    if use_locationiq:
        with st.spinner("Reverse geocoding current fleet positions..."):
            operational_df = reverse_geocode_dataframe(
                operational_df,
                lat_column="curr_lat",
                lon_column="curr_lon",
            )

        # Do not overwrite operational state unless the source state is blank.
        if "curr_state" not in operational_df.columns:
            operational_df["curr_state"] = ""

        if "geocoded_state" in operational_df.columns:
            blank_state = (
                operational_df["curr_state"]
                .fillna("")
                .astype(str)
                .str.strip()
                .eq("")
            )
            operational_df.loc[blank_state, "curr_state"] = (
                operational_df.loc[blank_state, "geocoded_state"]
            )

    try:
        evaluated_df = FleetRulesEngine.evaluate_fleet(
            operational_df,
            geofences=geofences,
        )

        evaluated_df = process_and_merge_safety_alerts(
            evaluated_df,
            alerts_df,
        )

        # Operational KPIs
        status_counts = evaluated_df["updated_status"].value_counts()

        c1, c2, c3, c4, c5 = st.columns(5)

        with c1:
            st.metric(
                "Yet to Start",
                int(status_counts.get("YET TO START", 0)),
            )

        with c2:
            st.metric(
                "Outbound",
                int(status_counts.get("OUTBOUND TO CUSTOMER", 0)),
            )

        with c3:
            st.metric(
                "At Customer",
                int(
                    status_counts.get(
                        "ARRIVED AT CUSTOMER LOCATION",
                        0,
                    )
                ),
            )

        with c4:
            st.metric(
                "Inbound",
                int(status_counts.get("INBOUND", 0)),
            )

        with c5:
            st.metric(
                "Completed",
                int(status_counts.get("COMPLETED", 0)),
            )

        # Alerts
        high_alerts = int(
            (evaluated_df["alert_flag"] == "HIGH_ALERT").sum()
        )
        location_warnings = int(
            (evaluated_df["alert_flag"] == "WARNING").sum()
        )
        critical_safety = int(
            (
                evaluated_df["Safety Score Risk"]
                == "CRITICAL_SAFETY_RISK"
            ).sum()
        )

        a1, a2, a3 = st.columns(3)

        with a1:
            st.metric("GPS High Alerts", high_alerts)

        with a2:
            st.metric("Lagos/Geofence Warnings", location_warnings)

        with a3:
            st.metric("Critical Safety Risks", critical_safety)

        if high_alerts:
            st.error(
                f"{high_alerts} vehicle(s) triggered a GPS anomaly. "
                "Driver verification is required."
            )

        critical_df = evaluated_df[
            evaluated_df["Safety Score Risk"]
            == "CRITICAL_SAFETY_RISK"
        ]

        if not critical_df.empty:
            st.warning(
                f"{len(critical_df)} vehicle(s) have critical "
                "driver-behavior risk indicators."
            )

            safety_columns = [
                column
                for column in [
                    "reg_number",
                    "trip_no",
                    "updated_status",
                    "curr_state",
                    "Total Alerts Today",
                    "Alert Types Summary",
                    "Safety Score Risk",
                ]
                if column in critical_df.columns
            ]

            st.dataframe(
                critical_df[safety_columns],
                use_container_width=True,
            )

        result_columns = [
            column
            for column in [
                "reg_number",
                "trip_no",
                "asset_status",
                "updated_status",
                "prev_state",
                "curr_state",
                "dest_state",
                "current_address",
                "distance_delta_km",
                "implied_speed_kmh",
                "alert_flag",
                "comment",
                "customer_arrival_date",
                "customer_departure_date",
                "refinery_arrival_date",
                "Total Alerts Today",
                "Alert Types Summary",
                "Safety Score Risk",
            ]
            if column in evaluated_df.columns
        ]

        st.subheader("Current In-Transit Report")
        st.dataframe(
            evaluated_df[result_columns],
            use_container_width=True,
            height=500,
        )

        # Shift audit
        st.divider()
        st.subheader("📋 Shift Audit & Handover Status")

        shift_meta = build_shift_metadata(
            shift_period=shift_period,
            operator_name=operator_name.strip() or "Unassigned",
            handover_status=handover_status,
            shift_notes=shift_notes,
            signed_off=sign_off_confirmed,
        )

        s1, s2, s3, s4 = st.columns(4)

        with s1:
            st.metric("Active Operative", shift_meta["Operative"])

        with s2:
            st.metric("Shift Period", shift_meta["Shift_Period"])

        with s3:
            st.metric(
                "Sign-Off",
                "SIGNED OFF"
                if shift_meta["Signed_Off"]
                else "IN PROGRESS",
            )

        with s4:
            st.metric(
                "Timestamp",
                shift_meta["Timestamp"].split()[1],
            )

        if shift_notes.strip():
            st.info(
                f"**Handover Note:** {shift_notes.strip()}"
            )

        if not sign_off_confirmed:
            st.warning(
                "Shift is unlocked. Confirm sign-off before exporting."
            )

        audited_df = append_audit_trail_to_export(
            evaluated_df,
            shift_meta,
        )

        csv_data = audited_df.to_csv(
            index=False
        ).encode("utf-8")

        excel_data = build_excel_export(audited_df)

        export_col1, export_col2 = st.columns(2)

        with export_col1:
            st.download_button(
                "📥 Export Signed Report (CSV)",
                data=csv_data,
                file_name="InTransit_Report.csv",
                mime="text/csv",
                disabled=not sign_off_confirmed,
                use_container_width=True,
            )

        with export_col2:
            st.download_button(
                "📊 Export Signed Report (Excel)",
                data=excel_data,
                file_name="InTransit_Report.xlsx",
                mime=(
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet"
                ),
                disabled=not sign_off_confirmed,
                use_container_width=True,
            )

    except Exception as exc:
        st.error(
            f"Operational pipeline failed: {exc}"
        )


st.divider()
st.caption(
    "GreenTag Fleet Logistics • Operational status terminology is "
    "standardized for the in-transit workflow."
)
