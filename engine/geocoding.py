import pandas as pd
import requests
import streamlit as st


LOCATIONIQ_URL = "https://us1.locationiq.com/v1/reverse"


def get_locationiq_key() -> str:
    """Read the LocationIQ key from Streamlit secrets without exposing it."""
    return (
        st.secrets.get("LOCATIONIQ_KEY", "")
        or st.secrets.get("LOCATIONIQ_API_KEY", "")
    )


@st.cache_data(ttl=86400, show_spinner=False)
def reverse_geocode_locationiq(lat, lon):
    """
    Reverse geocode a coordinate with LocationIQ.

    Returns:
        (display_address, state)
    """
    if pd.isna(lat) or pd.isna(lon):
        return "Invalid Coords", "UNKNOWN"

    api_key = get_locationiq_key()
    if not api_key:
        return "LocationIQ key not configured", "UNKNOWN"

    params = {
        "key": api_key,
        "lat": float(lat),
        "lon": float(lon),
        "format": "json",
    }

    try:
        response = requests.get(
            LOCATIONIQ_URL,
            params=params,
            timeout=8,
        )

        if response.status_code == 200:
            data = response.json()
            address_info = data.get("address", {})

            state = address_info.get(
                "state",
                address_info.get("region", "UNKNOWN"),
            )

            state_clean = str(state).replace(" State", "").strip().upper()
            display_name = data.get(
                "display_name",
                "Address not found",
            )

            return display_name, state_clean

        if response.status_code == 429:
            return "Rate Limit Exceeded", "UNKNOWN"

        return f"Geocoding Error ({response.status_code})", "UNKNOWN"

    except requests.RequestException as exc:
        return f"Geocoding Error: {exc}", "UNKNOWN"


def reverse_geocode_dataframe(
    df: pd.DataFrame,
    lat_column: str = "curr_lat",
    lon_column: str = "curr_lon",
) -> pd.DataFrame:
    """Add readable address/state fields to a fleet DataFrame."""
    result = df.copy()

    if lat_column not in result.columns or lon_column not in result.columns:
        result["current_address"] = "Coordinates unavailable"
        result["geocoded_state"] = "UNKNOWN"
        return result

    locations = result.apply(
        lambda row: reverse_geocode_locationiq(
            row[lat_column],
            row[lon_column],
        ),
        axis=1,
    )

    result["current_address"] = locations.map(lambda value: value[0])
    result["geocoded_state"] = locations.map(lambda value: value[1])

    return result
