import streamlit as st
import pandas as pd
import numpy as np

# Dealer Configuration Dictionary
DEALER_CONFIG = {
    "APACHE2026": {
        "name": "Apache Camping Center",
        "logo_icon": "rv-icon.png",
        "csv_path": "apache_full_inventory.csv"
    }
}

# License Key Validation
query_params = st.query_params
license_key = query_params.get("key", "APACHE2026")
dealer_info = DEALER_CONFIG.get(license_key, DEALER_CONFIG["APACHE2026"])

# Page Setup
st.set_page_config(
    page_title=f"{dealer_info['name']} - Tow Match Pro",
    page_icon=dealer_info["logo_icon"],
    layout="wide"
)

# Header
st.title(f"🚐 {dealer_info['name']} — Tow Match Pro")
st.caption("Match customer tow vehicle capacity against live lot inventory.")

# Load and Clean Inventory Data
@st.cache_data(ttl=600)
def load_inventory(filepath):
    try:
        data = pd.read_csv(filepath)
    except Exception:
        return pd.DataFrame()

    # Ensure required columns exist
    for col in ["Length", "DryWeight", "GVWR", "HitchWeight"]:
        if col not in data.columns:
            data[col] = np.nan

    # Convert numeric fields
    for col in ["Length", "DryWeight", "GVWR", "HitchWeight"]:
        data[col] = pd.to_numeric(data[col], errors="coerce")

    # Clean Lengths: convert values given in inches (> 45) to decimal feet
    data["Length"] = data["Length"].apply(
        lambda x: round(x / 12.0, 1) if pd.notnull(x) and x > 45 else (round(x, 1) if pd.notnull(x) else 26.0)
    )

    # Clean and fill fallback weights if unlisted
    data["DryWeight"] = data["DryWeight"].fillna(5200)
    data["GVWR"] = data["GVWR"].fillna(data["DryWeight"] + 1800)
    data["HitchWeight"] = data["HitchWeight"].fillna((data["GVWR"] * 0.12).round())

    return data

df_raw = load_inventory(dealer_info["csv_path"])

if df_raw.empty:
    st.error("Unable to load inventory data. Please verify 'apache_full_inventory.csv' is uploaded.")
    st.stop()

# Layout: Two-Column Form
col1, col2 = st.columns(2)

with col1:
    st.subheader("1. Tow Vehicle Specs")
    entry_method = st.radio("Entry Method:", ["Door Placard (Fastest)", "Desk Lookup"], horizontal=True)

    sticker_payload = st.number_input(
        "Sticker Payload (Yellow Tag lbs)",
        min_value=500,
        max_value=8000,
        value=1650,
        step=50
    )
    truck_gvwr = st.number_input(
        "Truck GVWR (Safety Tag lbs)",
        min_value=3000,
        max_value=20000,
        value=7100,
        step=50
    )

with col2:
    st.subheader("2. Trip Loading & Passengers")
    towable_style = st.radio("Towable Style:", ["Travel Trailer (Bumper Pull)", "Fifth Wheel"], horizontal=True)
    occupants = st.number_input("Occupants in Truck (Total Count)", min_value=1, max_value=8, value=2, step=1)
    bed_cargo = st.number_input("Bed Cargo / Gear (lbs)", min_value=0, max_value=2500, value=150, step=25)
    hitch_hardware = st.number_input("Hitch Hardware Weight (lbs)", min_value=0, max_value=350, value=65, step=5)

# Sidebar Filter Controls
st.sidebar.header("Inventory Filters")
max_len_filter = st.sidebar.slider(
    "Max Trailer Length (ft)",
    min_value=int(df_raw["Length"].min()),
    max_value=int(df_raw["Length"].max()),
    value=int(df_raw["Length"].max()),
    step=1
)

max_budget = st.sidebar.slider(
    "Max Hitch Weight Allowed (lbs)",
    min_value=200,
    max_value=2500,
    value=1500,
    step=50
)

# Capacity Calculations
passenger_allowance = occupants * 175
total_truck_occupant_cargo = passenger_allowance + bed_cargo + hitch_hardware
available_payload = sticker_payload - total_truck_occupant_cargo

st.markdown("---")
st.subheader("Vehicle Towing Envelope")

m1, m2, m3 = st.columns(3)
m1.metric("Gross Available Payload", f"{available_payload:,} lbs")
m2.metric("Occupant & Gear Load", f"{total_truck_occupant_cargo:,} lbs")
m3.metric("Max Tongue Weight Budget", f"{max(0, available_payload):,} lbs")

if available_payload <= 0:
    st.error("Warning: Passenger and bed cargo load exceeds vehicle sticker payload before attaching a trailer.")

# Filter Matches
is_bumper = towable_style == "Travel Trailer (Bumper Pull)"

# Tongue calculation: use explicit hitch weight or estimate 12% of GVWR
df_matches = df_raw.copy()
df_matches["EstTongue"] = df_matches["HitchWeight"].fillna(df_matches["GVWR"] * 0.12)

# Apply limits
df_filtered = df_matches[
    (df_matches["Length"] <= max_len_filter) &
    (df_matches["EstTongue"] <= available_payload) &
    (df_matches["EstTongue"] <= max_budget)
].copy()

st.markdown("---")
st.subheader(f"Matching Inventory ({len(df_filtered)} Units Available)")

# Output Table
display_cols = ["Model", "Length", "DryWeight", "GVWR", "HitchWeight", "URL"]
display_cols = [c for c in display_cols if c in df_filtered.columns]

st.dataframe(
    df_filtered[display_cols].rename(columns={
        "Length": "Length (ft)",
        "DryWeight": "Dry (lbs)",
        "GVWR": "GVWR (lbs)",
        "HitchWeight": "Hitch (lbs)"
    }),
    use_container_width=True,
    hide_index=True
)
