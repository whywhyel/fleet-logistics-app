import numpy as np
import pandas as pd
from datetime import datetime
from math import radians, cos, sin, asin, sqrt


# Refinery / terminal geofences.
# Coordinates and radii are configuration values and should be verified
# against the organization's operational gate coordinates before production use.
TERMINAL_GEOFENCES = {
    "LAGOS_REFINERY_MAIN": {"lat": 6.4531, "lon": 3.3958, "radius_km": 2.5},
    "DANGOTE_REFINERY_LEKKI": {"lat": 6.4350, "lon": 3.8820, "radius_km": 3.0},
    "IBADAN_DEPOT": {"lat": 7.3775, "lon": 3.9470, "radius_km": 2.0},
}

TRANSIT_STATES = ["ONDO", "OGUN", "EDO", "OYO", "DELTA", "KWARA", "KOGI"]


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    """Calculate great-circle distance between two points in kilometres."""
    try:
        values = [float(lat1), float(lon1), float(lat2), float(lon2)]
        if not all(np.isfinite(value) for value in values):
            return np.nan

        lat1, lon1, lat2, lon2 = map(radians, values)
        dlon = lon2 - lon1
        dlat = lat2 - lat1

        a = (
            sin(dlat / 2) ** 2
            + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        )
        a = min(1.0, max(0.0, a))
        c = 2 * asin(sqrt(a))

        return c * 6371.0

    except (ValueError, TypeError, OverflowError):
        return np.nan


def check_geofence(lat, lon) -> tuple:
    """Return whether coordinates are inside an active terminal geofence."""
    if pd.isna(lat) or pd.isna(lon):
        return False, None, np.nan

    for name, fence in TERMINAL_GEOFENCES.items():
        distance = haversine_km(
            lat,
            lon,
            fence["lat"],
            fence["lon"],
        )

        if pd.notna(distance) and distance <= fence["radius_km"]:
            return True, name, distance

    return False, None, np.nan


class FleetRulesEngine:
    """
    Evaluates controlled trip-state transitions, GPS anomalies,
    and terminal geofence completion events.
    """

    MAX_IMPLIED_SPEED_KMH = 85.0
    DEPARTURE_DISTANCE_KM = 15.0
    CUSTOMER_DEPARTURE_DISTANCE_KM = 20.0

    @staticmethod
    def _value(row, key, default=None):
        value = row.get(key, default)
        return default if pd.isna(value) else value

    @classmethod
    def process_row(cls, row, hours_elapsed=14.0) -> dict:
        prev_status = str(
            cls._value(row, "asset_status", "")
        ).strip().upper()

        prev_state = str(
            cls._value(row, "prev_state", "")
        ).strip().upper()

        curr_state = str(
            cls._value(row, "curr_state", "")
        ).strip().upper()

        dest_state = str(
            cls._value(row, "dest_state", "")
        ).strip().upper()

        prev_lat = cls._value(row, "prev_lat")
        prev_lon = cls._value(row, "prev_lon")
        curr_lat = cls._value(row, "curr_lat")
        curr_lon = cls._value(row, "curr_lon")

        today_str = datetime.now().strftime("%m/%d/%Y")

        distance_km = haversine_km(
            prev_lat,
            prev_lon,
            curr_lat,
            curr_lon,
        )

        implied_speed = (
            distance_km / hours_elapsed
            if pd.notna(distance_km) and hours_elapsed > 0
            else 0.0
        )

        new_status = prev_status
        customer_arrival_date = cls._value(
            row, "customer_arrival_date"
        )
        refinery_arrival_date = cls._value(
            row, "refinery_arrival_date"
        )
        comment = ""
        alert_flag = "NORMAL"

        # GPS anomaly / possible teleportation.
        if implied_speed > cls.MAX_IMPLIED_SPEED_KMH:
            return {
                "updated_status": prev_status,
                "customer_arrival_date": customer_arrival_date,
                "refinery_arrival_date": refinery_arrival_date,
                "comment": (
                    f"SPOOF ALERT: Jumped {distance_km:.0f}km at "
                    f"{implied_speed:.0f}km/h. Call Driver."
                ),
                "alert_flag": "HIGH_ALERT",
                "distance_delta_km": distance_km,
                "implied_speed_kmh": implied_speed,
            }

        # YET TO START -> OUTBOUND / same-day destination handling.
        if prev_status == "YET TO START":
            departed = (
                pd.notna(distance_km)
                and distance_km > cls.DEPARTURE_DISTANCE_KM
            )
            state_changed = (
                bool(curr_state)
                and curr_state != prev_state
            )

            if departed or state_changed:
                if curr_state == dest_state and dest_state == "LAGOS":
                    new_status = "ARRIVED AT CUSTOMER LOCATION"
                    customer_arrival_date = today_str
                    comment = "Same-day Lagos trip completed"
                    alert_flag = "INFO"
                else:
                    new_status = "OUTBOUND TO CUSTOMER"
                    comment = "Transit initiated"
                    alert_flag = "INFO"
            else:
                comment = "Pending departure from base"

        # OUTBOUND -> ARRIVED AT CUSTOMER LOCATION.
        elif prev_status == "OUTBOUND TO CUSTOMER":
            if curr_state == dest_state and curr_state:
                new_status = "ARRIVED AT CUSTOMER LOCATION"
                customer_arrival_date = today_str
                comment = (
                    f"Arrived at destination state ({dest_state})"
                )
                alert_flag = "INFO"
            else:
                comment = f"In-transit to {dest_state}"

        # ARRIVED -> INBOUND.
        elif prev_status == "ARRIVED AT CUSTOMER LOCATION":
            departed_customer = (
                pd.notna(distance_km)
                and distance_km > cls.CUSTOMER_DEPARTURE_DISTANCE_KM
            )
            left_destination_state = (
                bool(curr_state)
                and curr_state != dest_state
            )

            if departed_customer or left_destination_state:
                new_status = "INBOUND"
                comment = (
                    f"Departed customer location "
                    f"(Departure Date: {today_str})"
                )
                alert_flag = "INFO"
            else:
                comment = "AWAITING DISCHARGE / DISPUTE"

        # INBOUND -> COMPLETED when a terminal geofence is reached.
        elif prev_status == "INBOUND":
            at_geofence, terminal_name, fence_distance = check_geofence(
                curr_lat,
                curr_lon,
            )

            if at_geofence:
                new_status = "COMPLETED"
                refinery_arrival_date = today_str
                comment = (
                    f"Arrived at {terminal_name} "
                    f"({fence_distance:.2f}km from gate)"
                )
                alert_flag = "COMPLETED"

            elif curr_state in TRANSIT_STATES:
                comment = f"Inbound transit via {curr_state}"

            elif curr_state == "LAGOS":
                comment = "Within Lagos - Verify terminal entrance"
                alert_flag = "WARNING"

            else:
                comment = f"Inbound transit via {curr_state}"

        return {
            "updated_status": new_status,
            "customer_arrival_date": customer_arrival_date,
            "refinery_arrival_date": refinery_arrival_date,
            "comment": comment,
            "alert_flag": alert_flag,
            "distance_delta_km": (
                distance_km if pd.notna(distance_km) else 0.0
            ),
            "implied_speed_kmh": implied_speed,
        }

    @classmethod
    def evaluate_fleet(cls, df_merged: pd.DataFrame) -> pd.DataFrame:
        """Run the rules engine across the fleet dataset."""
        results = []

        for _, row in df_merged.iterrows():
            evaluation = cls.process_row(row)
            result = row.to_dict()
            result.update(evaluation)
            results.append(result)

        return pd.DataFrame(results)
