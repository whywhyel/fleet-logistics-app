import streamlit as st

from engine.data_ingestion import FleetDataIngestor


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
    "Step 2 is active: upload VTS and previous evening report files "
    "for controlled ingestion and normalization."
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

if vts_file is not None:
    try:
        vts_df = FleetDataIngestor.process_vts_export(vts_file)

        st.success(
            f"VTS file processed successfully: {len(vts_df):,} vehicle records."
        )

        with st.expander("Preview normalized VTS data", expanded=True):
            st.dataframe(vts_df.head(50), use_container_width=True)

    except Exception as exc:
        st.error(f"Unable to process VTS file: {exc}")

if previous_report is not None:
    try:
        report_df = FleetDataIngestor.process_previous_report(previous_report)

        st.success(
            "Previous evening report processed successfully: "
            f"{len(report_df):,} active records retained."
        )

        with st.expander(
            "Preview normalized previous evening report",
            expanded=True,
        ):
            st.dataframe(report_df.head(50), use_container_width=True)

    except Exception as exc:
        st.error(f"Unable to process previous evening report: {exc}")

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
