# Fleet Logistics App

A Streamlit-based fleet and logistics operations application for GreenTag Solutions.

## Purpose

The application automates the daily oil & gas fleet in-transit workflow:

- VTS fleet-position ingestion
- Previous evening report processing
- Driver-behavior alert integration
- LocationIQ reverse geocoding
- Controlled asset-status transitions
- GPS anomaly detection
- Refinery / terminal geofencing
- Shift handover and operator sign-off
- CSV and Excel operational reporting

## Project Structure

```text
fleet-logistics-app/
├── .streamlit/
│   └── secrets.toml.example
├── engine/
│   ├── audit.py
│   ├── data_ingestion.py
│   ├── geocoding.py
│   ├── rules_engine.py
│   └── safety.py
├── app.py
├── requirements.txt
├── .gitignore
└── README.md
```

## Standard Asset Statuses

The application uses the following operational terminology:

| Status | Operational definition |
|---|---|
| `YET TO START` | Scheduled trip; truck has not moved from base. |
| `OUTBOUND TO CUSTOMER` | Truck is travelling toward the customer destination. |
| `ARRIVED AT CUSTOMER LOCATION` | Truck has reached the destination state according to the current location data. |
| `INBOUND` | Truck has departed the customer location and is returning toward base. |
| `COMPLETED` | Truck has entered a configured company/refinery/depot geofence. |

Automated transitions are recorded with an operational comment and alert classification.

## Core Rules

### Customer arrival

When the current location state matches the destination state, an outbound trip can transition to:

`ARRIVED AT CUSTOMER LOCATION`

The customer arrival date is stamped using `MM/DD/YYYY`.

### Customer departure

When an arrived vehicle moves sufficiently away from the customer location or leaves the destination state, it can transition to:

`INBOUND`

The engine records a customer departure date.

### GPS anomaly

The rules engine calculates the great-circle distance between the previous and current coordinates. An implied speed above the configured heavy-truck threshold of 85 km/h is flagged as:

`HIGH_ALERT`

The status is not automatically advanced when this anomaly is detected.

### Terminal completion

An `INBOUND` vehicle is checked against the configured terminal geofences. Entering a geofence produces:

`COMPLETED`

and stamps the refinery/terminal arrival date.

The coordinates and radii in `engine/rules_engine.py` are configuration values and must be verified against GreenTag's approved operational gate coordinates before production use.

## LocationIQ

LocationIQ can be used for cached reverse geocoding of current vehicle coordinates.

Create:

`.streamlit/secrets.toml`

from the example:

`.streamlit/secrets.toml.example`

and configure:

```toml
LOCATIONIQ_KEY = "YOUR_LOCATIONIQ_API_KEY"
```

The application also recognizes `LOCATIONIQ_API_KEY` for compatibility.

Real secrets must never be committed.

## Driver Behavior Integration

The application accepts CSV/XLS/XLSX safety-alert exports and aggregates events by vehicle registration where available.

It can identify:

- Fatigue / drowsiness events
- Phone / distraction events
- Speeding / overspeed events
- Total alerts
- Alert-type summary
- Safety risk classification

Safety indicators are displayed alongside the fleet in-transit report.

## Shift Handover

The application captures:

- Active operative
- Shift period
- Handover status
- Handover notes
- Sign-off confirmation
- Timestamp

Exports remain disabled until the operator confirms sign-off.

## Data Handling

Uploaded operational files are processed during the Streamlit session. No real operational data or API keys are hard-coded into the repository.

## Technology Stack

- Python
- Streamlit
- Pandas
- NumPy
- OpenPyXL
- Reverse Geocoder
- Geopy
- Requests

## Development

The application is being built incrementally. The current foundation contains the ingestion, rules, geocoding, safety-alert, geofence and shift-audit layers without requiring fake operational data.
