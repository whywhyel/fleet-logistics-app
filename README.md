# Fleet Logistics App

A Streamlit-based fleet and logistics operations application for GreenTag Solutions.

## Initial Project Structure

```text
fleet-logistics-app/
├── .streamlit/
│   └── secrets.toml          # Local API keys; never commit real secrets
├── app.py
├── requirements.txt
├── .gitignore
└── README.md
```

## Technology Stack

- Python
- Streamlit
- Pandas
- NumPy
- OpenPyXL
- Reverse Geocoder
- Geopy
- Requests

## Local Setup

Clone the repository:

```bash
git clone https://github.com/whywhyel/fleet-logistics-app.git
cd fleet-logistics-app
```

Create a virtual environment if desired:

```bash
python -m venv .venv
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the application:

```bash
streamlit run app.py
```

## Secrets

Create this local file:

`.streamlit/secrets.toml`

Example:

```toml
LOCATIONIQ_API_KEY = ""
```

Do not commit real API keys or credentials.

## Development Direction

The application will be built incrementally around fleet operations, including:

1. Vehicle and trip data ingestion
2. Vehicle location processing
3. Reverse geocoding
4. Fleet status monitoring
5. Delivery/order tracking
6. Trip behaviour and route analysis
7. Operational alerts and stale-data detection
8. Reporting and Excel export

The initial application intentionally contains no fake operational data.
