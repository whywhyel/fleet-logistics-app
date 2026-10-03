import streamlit as st


st.set_page_config(
    page_title="GreenTag Fleet Logistics",
    page_icon="🚛",
    layout="wide",
)


st.title("🚛 GreenTag Fleet Logistics")
st.caption("Fleet operations, vehicle location, trip monitoring and logistics control.")


st.info(
    "Project initialized. The fleet rules engine and operational modules will be built here."
)


st.subheader("System Status")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Application", "Ready")

with col2:
    st.metric("Data Source", "Not connected")

with col3:
    st.metric("Location Service", "Not configured")


st.divider()

st.write(
    "This is the clean starting point for the Fleet Logistics App. "
    "No operational data is hard-coded into the application."
)
