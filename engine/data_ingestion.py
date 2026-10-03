import pandas as pd
import numpy as np


class FleetDataIngestor:
    """
    Handles file loading, column harmonization, date standardization,
    and coordinate cleaning for VTS and evening report files.
    """

    EXPECTED_COLUMNS = {
        "reg_number": [
            "vehicle registration number",
            "reg number",
            "plate number",
            "asset",
            "vehicle_reg",
        ],
        "asset_status": [
            "asset status",
            "status",
            "current status",
            "trip status",
        ],
        "prev_state": [
            "previous location state",
            "prev state",
            "last known state",
        ],
        "curr_state": [
            "current location state",
            "curr state",
            "state",
        ],
        "dest_state": [
            "destination state",
            "dest state",
            "delivery state",
        ],
        "lat": ["latitude", "lat", "curr lat", "y"],
        "lon": ["longitude", "lon", "lng", "curr lon", "x"],
        "trip_no": ["trip number", "trip id", "waybill number", "trip_no"],
    }

    @staticmethod
    def load_file(file_obj) -> pd.DataFrame:
        """Load a CSV or Excel upload into a DataFrame."""
        filename = (
            file_obj.name.lower()
            if hasattr(file_obj, "name")
            else str(file_obj).lower()
        )

        if filename.endswith(".csv"):
            return pd.read_csv(file_obj)

        if filename.endswith((".xlsx", ".xls")):
            return pd.read_excel(file_obj)

        raise ValueError(
            "Unsupported file format. Please upload a .csv or .xlsx file."
        )

    @classmethod
    def harmonize_columns(cls, df: pd.DataFrame) -> pd.DataFrame:
        """Map varied source headers to standardized internal column names."""
        renamed_cols = {}
        df_cols_lower = {
            col: str(col).strip().lower() for col in df.columns
        }

        for standard_key, aliases in cls.EXPECTED_COLUMNS.items():
            for orig_col, clean_col in df_cols_lower.items():
                if clean_col in aliases or any(
                    alias in clean_col for alias in aliases
                ):
                    renamed_cols[orig_col] = standard_key
                    break

        return df.rename(columns=renamed_cols)

    @staticmethod
    def normalize_dates(series: pd.Series) -> pd.Series:
        """Standardize dates to MM/DD/YYYY strings."""

        def parse_date(val):
            if pd.isna(val) or val == "":
                return None

            if str(val).strip().upper() == "NAN":
                return None

            try:
                dt = pd.to_datetime(val, errors="coerce")
                if pd.notnull(dt):
                    return dt.strftime("%m/%d/%Y")
            except (TypeError, ValueError, OverflowError):
                pass

            return None

        return series.apply(parse_date)

    @staticmethod
    def clean_coordinates(df: pd.DataFrame) -> pd.DataFrame:
        """Parse and validate numeric latitude and longitude values."""
        df = df.copy()

        if "lat" in df.columns:
            df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
            df.loc[(df["lat"] < -90) | (df["lat"] > 90), "lat"] = np.nan

        if "lon" in df.columns:
            df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
            df.loc[(df["lon"] < -180) | (df["lon"] > 180), "lon"] = np.nan

        return df

    @staticmethod
    def normalize_registration(series: pd.Series) -> pd.Series:
        """Normalize vehicle registration values for reliable joins."""
        return (
            series.astype("string")
            .str.strip()
            .str.upper()
            .str.replace(r"\s+", " ", regex=True)
        )

    @classmethod
    def process_vts_export(cls, file_obj) -> pd.DataFrame:
        """
        Process a VTS export:
        - Load the file.
        - Harmonize headers.
        - Normalize registration numbers.
        - Deduplicate by vehicle registration.
        - Clean coordinates.
        """
        df = cls.load_file(file_obj)
        df = cls.harmonize_columns(df)

        if "reg_number" in df.columns:
            df["reg_number"] = cls.normalize_registration(df["reg_number"])
            df = df.drop_duplicates(subset=["reg_number"], keep="last")

        return cls.clean_coordinates(df)

    @classmethod
    def process_previous_report(cls, file_obj) -> pd.DataFrame:
        """
        Process a previous evening report:
        - Harmonize headers.
        - Normalize registration numbers.
        - Remove completed trips.
        - Standardize date columns.
        """
        df = cls.load_file(file_obj)
        df = cls.harmonize_columns(df)

        if "reg_number" in df.columns:
            df["reg_number"] = cls.normalize_registration(df["reg_number"])

        if "asset_status" in df.columns:
            df["asset_status"] = (
                df["asset_status"]
                .astype("string")
                .str.strip()
                .str.upper()
            )
            df = df[df["asset_status"] != "COMPLETED"].copy()

        date_cols = [col for col in df.columns if "date" in col.lower()]
        for col in date_cols:
            df[col] = cls.normalize_dates(df[col])

        return cls.clean_coordinates(df)
