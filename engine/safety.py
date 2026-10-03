import pandas as pd


def _find_column(columns, keywords):
    for column in columns:
        clean = str(column).strip().lower()
        if any(keyword in clean for keyword in keywords):
            return column
    return None


def process_and_merge_safety_alerts(
    df_intransit: pd.DataFrame,
    df_alerts: pd.DataFrame | None,
) -> pd.DataFrame:
    """
    Aggregate driver-behavior alerts and merge them onto the in-transit report.

    Matching is primarily by normalized vehicle registration number.
    """
    result = df_intransit.copy()

    if "reg_number" not in result.columns:
        result["Safety Score Risk"] = "NORMAL"
        result["Total Alerts Today"] = 0
        result["Alert Types Summary"] = "Vehicle ID unavailable"
        return result

    if df_alerts is None or df_alerts.empty:
        result["Safety Score Risk"] = "NORMAL"
        result["Total Alerts Today"] = 0
        result["Alert Types Summary"] = "Clear / No Incidents"
        return result

    alerts = df_alerts.copy()
    alerts.columns = [str(column).strip() for column in alerts.columns]

    vehicle_column = _find_column(
        alerts.columns,
        ["reg", "vehicle", "asset", "plate"],
    )
    trip_column = _find_column(
        alerts.columns,
        ["trip", "waybill"],
    )
    alert_type_column = _find_column(
        alerts.columns,
        ["alert", "event", "behavior", "violation"],
    )

    if vehicle_column is None and trip_column is None:
        raise ValueError(
            "Could not locate a vehicle registration or trip number "
            "column in the Driver Behavior Alerts export."
        )

    if alert_type_column is None:
        alert_type_column = "Alert_Type"
        alerts[alert_type_column] = "Unclassified Alert"

    if vehicle_column is not None:
        alerts["_join_vehicle"] = (
            alerts[vehicle_column]
            .astype("string")
            .str.strip()
            .str.upper()
            .str.replace(r"\s+", " ", regex=True)
        )

        result["_join_vehicle"] = (
            result["reg_number"]
            .astype("string")
            .str.strip()
            .str.upper()
            .str.replace(r"\s+", " ", regex=True)
        )

        summary = alerts.groupby("_join_vehicle").agg(
            Total_Alerts=(alert_type_column, "count"),
            Alert_List=(
                alert_type_column,
                lambda values: ", ".join(
                    dict.fromkeys(str(value) for value in values)
                ),
            ),
            Fatigue_Events=(
                alert_type_column,
                lambda values: sum(
                    1
                    for value in values
                    if any(
                        word in str(value).lower()
                        for word in ["fatigue", "yawn", "drowsy"]
                    )
                ),
            ),
            Phone_Use_Events=(
                alert_type_column,
                lambda values: sum(
                    1
                    for value in values
                    if any(
                        word in str(value).lower()
                        for word in ["phone", "distraction", "mobile"]
                    )
                ),
            ),
            Speeding_Events=(
                alert_type_column,
                lambda values: sum(
                    1
                    for value in values
                    if any(
                        word in str(value).lower()
                        for word in ["speed", "overspeed"]
                    )
                ),
            ),
        ).reset_index()

        def assign_risk(row):
            if (
                row["Fatigue_Events"] > 0
                or row["Phone_Use_Events"] > 1
                or row["Total_Alerts"] >= 5
            ):
                return "CRITICAL_SAFETY_RISK"

            if (
                row["Phone_Use_Events"] == 1
                or row["Speeding_Events"] >= 2
            ):
                return "MEDIUM_RISK"

            if row["Total_Alerts"] > 0:
                return "LOW_RISK"

            return "NORMAL"

        summary["Safety Score Risk"] = summary.apply(
            assign_risk,
            axis=1,
        )

        result = result.merge(
            summary,
            left_on="_join_vehicle",
            right_on="_join_vehicle",
            how="left",
        )

    else:
        # Trip-only fallback when the alert export has no vehicle ID.
        result["_join_trip"] = (
            result["trip_no"].astype("string")
            if "trip_no" in result.columns
            else pd.Series(index=result.index, dtype="string")
        )
        alerts["_join_trip"] = alerts[trip_column].astype("string")

        summary = alerts.groupby("_join_trip").agg(
            Total_Alerts=(alert_type_column, "count"),
            Alert_List=(
                alert_type_column,
                lambda values: ", ".join(
                    dict.fromkeys(str(value) for value in values)
                ),
            ),
        ).reset_index()

        summary["Safety Score Risk"] = summary["Total_Alerts"].map(
            lambda count: "CRITICAL_SAFETY_RISK"
            if count >= 5
            else "LOW_RISK"
        )

        result = result.merge(
            summary,
            on="_join_trip",
            how="left",
        )

    result["Total Alerts Today"] = (
        result["Total_Alerts"].fillna(0).astype(int)
    )
    result["Alert Types Summary"] = result["Alert_List"].fillna(
        "Clear / No Incidents"
    )
    result["Safety Score Risk"] = result["Safety Score Risk"].fillna(
        "NORMAL"
    )

    return result.drop(
        columns=[
            "_join_vehicle",
            "_join_trip",
            "Total_Alerts",
            "Alert_List",
            "Fatigue_Events",
            "Phone_Use_Events",
            "Speeding_Events",
        ],
        errors="ignore",
    )
