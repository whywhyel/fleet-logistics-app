import streamlit as st

from engine.data_ingestion import FleetDataIngestor
from engine.rules_engine import FleetRulesEngine


st.set_page_config(
    page_title="GreenTag Fleet Logistics",
    page_icon="🚛",
    layout="wide",
)

st.title("🚛 GreenTag Fleet Logistics")
st.caption(
    "Oil & gas fleet in-transit monitoring and logistics automation."
)

st.info(
    "Phase 2 active: ingestion, trip-state evaluation, GPS anomaly "
    "detection and terminal geofence checks."
)

st.subheader("Fleet Data Ingestion")

vts_file = st.file_uploader(
    "VTS Export",
    type=["csv", "xlsx", "xls"],
    key="vts_upload",
)

previous_report = st.file_uploader(
    "Previous Evening Report",
    type=["csv", "xlsx", "xls"],
    key="previous_report_upload",
)

vts_df = None
report_df = None

if vts_file is not None:
    try:
        vts_df = FleetDataIngestor.process_vts_export(vts_file)

        st.success(
            f"VTS file processed successfully: "
            f"{len(vts_df):,} vehicle records."
        )

        with st.expander("Preview normalized VTS data", expanded=True):
            st.dataframe(
                vts_df.head(50),
                use_container_width=True,
            )

    except Exception as exc:
        st.error(f"Unable to process VTS file: {exc}")

if previous_report is not None:
    try:
        report_df = FleetDataIngestor.process_previous_report(
            previous_report
        )

        st.success(
            "Previous evening report processed successfully: "
            f"{len(report_df):,} active records retained."
        )

        with st.expander(
            "Preview normalized previous evening report",
            expanded=True,
        ):
            st.dataframe(
                report_df.head(50),
                use_container_width=True,
            )

    except Exception as exc:
        st.error(f"Unable to process previous evening report: {exc}")


st.divider()

st.subheader("Phase 2 Rules Evaluation")

if report_df is not None:
    # The rules engine expects current and previous coordinates.
    # If the uploaded report does not contain them, it will safely
    # evaluate the available state information without inventing data.
    required_coordinate_columns = {
        "prev_lat",
        "prev_lon",
        "curr_lat",
        "curr_lon",
    }

    missing_coordinate_columns = (
        required_coordinate_columns - set(report_df.columns)
    )

    if missing_coordinate_columns:
        st.warning(
            "Rules evaluation requires previous/current GPS columns: "
            + ", ".join(sorted(missing_coordinate_columns))
            + ". State-based processing can still be inspected, "
            "but GPS distance, speed and geofence checks may be unavailable."
        )

    try:
        evaluated_df = FleetRulesEngine.evaluate_fleet(report_df)

        high_alerts = int(
            (evaluated_df["alert_flag"] == "HIGH_ALERT").sum()
        )
        completed = int(
            (evaluated_df["updated_status"] == "COMPLETED").sum()
        )
        warnings = int(
            (evaluated_df["alert_flag"] == "WARNING").sum()
        )

        metric1, metric2, metric3 = st.columns(3)

        with metric1:
            st.metric("High GPS Alerts", high_alerts)

        with metric2:
            st.metric("Completion Events", completed)

        with metric3:
            st.metric("Location Warnings", warnings)

        with st.expander(
            "Preview rules-engine results",
            expanded=True,
        ):
            result_columns = [
                column
                for column in [
                    "reg_number",
                    "trip_no",
                    "asset_status",
                    "updated_status",
                    "curr_state",
                    "dest_state",
                    "distance_delta_km",
                    "implied_speed_kmh",
                    "alert_flag",
                    "comment",
                    "customer_arrival_date",
                    "refinery_arrival_date",
                ]
                if column in evaluated_df.columns
            ]

            st.dataframe(
                evaluated_df[result_columns].head(100),
                use_container_width=True,
            )

    except Exception as exc:
        st.error(f"Rules engine evaluation failed: {exc}")

else:
    st.info(
        "Upload a Previous Evening Report to run the Phase 2 rules engine."
    )


st.divider()

st.subheader("System Status")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Application", "Ready")

with col2:
    st.metric(
        "Data Source",
        "Connected" if vts_file or previous_report else "Waiting for upload",
    )

with col3:
    st.metric("Location Service", "Offline-ready")

st.caption(
    "No operational data is stored in the repository. Uploaded files are "
    "processed in the application session."
)
