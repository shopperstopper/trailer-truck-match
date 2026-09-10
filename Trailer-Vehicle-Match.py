import os
import re
import pandas as pd
import streamlit as st

DEALER_ACCOUNTS = {
    "APACHE2026": {
        "name": "Apache Camping Center",
        "tagline": "Portland / Clackamas • Everett • Kitsap / Poulsbo • Tacoma",
        "primary_color": "#7A1C2E",
        "secondary_color": "#F9F1F2",
        "accent_color": "#9E2A40",
        "logo_icon": "⛺",
        "default_lot": "Portland / Clackamas",
        "csv_file": "apache_full_inventory.csv",
        "inventory": [],
    },
    "SUMMIT2026": {
        "name": "Summit RV Center",
        "tagline": "Family Owned & Operated Since 1994",
        "primary_color": "#1B5E20",
        "secondary_color": "#E8F5E9",
        "accent_color": "#2E7D32",
        "logo_icon": "🌲",
        "default_lot": "Main Lot",
        "csv_file": None,
        "inventory": [
            {
                "Stock": "T-4011",
                "Condition": "New",
                "Status": "On Lot",
                "Type": "Travel Trailer",
                "Year": 2026,
                "Model": "Grand Design Imagine 2600RB",
                "Length": 29,
                "DryWeight": 5725,
                "GVWR": 7495,
                "Price": "$34,995",
                "Location": "Main Lot",
                "Image": "https://images.unsplash.com/photo-1523987355523-c7b5b0dd90a7?auto=format&fit=crop&w=400&q=80",
            },
        ],
    },
}

TRUCK_FALLBACK_GUIDE = {
    "Ford": {
        "F-150 SuperCrew 4x4 (3.5L EcoBoost)": {"payload": 1600, "gvwr": 7050},
        "F-150 SuperCrew 4x4 (5.0L V8)": {"payload": 1650, "gvwr": 7050},
        "F-250 Crew Cab 4x4 (6.7L Diesel)": {"payload": 2350, "gvwr": 10000},
        "F-250 Crew Cab 4x4 (7.3L Gas)": {"payload": 3200, "gvwr": 10000},
        "F-350 SRW Crew Cab (6.7L Diesel)": {"payload": 3900, "gvwr": 11500},
    },
    "Chevrolet / GMC": {
        "Silverado 1500 Crew (5.3L V8)": {"payload": 1700, "gvwr": 7100},
        "Silverado 1500 Crew (3.0L Duramax)": {"payload": 1550, "gvwr": 7200},
        "Silverado 2500HD Crew (6.6L Diesel)": {"payload": 2850, "gvwr": 10650},
        "Silverado 2500HD Crew (6.6L Gas)": {"payload": 3400, "gvwr": 10450},
    },
    "Ram": {
        "Ram 1500 Crew 4x4 (5.7L Hemi)": {"payload": 1500, "gvwr": 6900},
        "Ram 2500 Crew 4x4 (6.7L Cummins)": {"payload": 2150, "gvwr": 10000},
        "Ram 2500 Crew 4x4 (6.4L Hemi)": {"payload": 3100, "gvwr": 10000},
        "Ram 3500 SRW (6.7L Cummins)": {"payload": 4100, "gvwr": 11800},
    },
    "Toyota": {
        "Tundra CrewMax 4x4 (3.4L TT V6)": {"payload": 1450, "gvwr": 7200},
    },
}

if "authenticated_dealer" not in st.session_state:
    st.session_state.authenticated_dealer = None

if not st.session_state.authenticated_dealer:
    query_key = st.query_params.get("key", "").upper()
    if query_key in DEALER_ACCOUNTS:
        st.session_state.authenticated_dealer = query_key

if not st.session_state.authenticated_dealer:
    st.set_page_config(page_title="TowMatch Pro | Dealer Access", page_icon="🔑", layout="centered")
    st.markdown("## 🚐 TowMatch Pro")
    with st.form("activation_form"):
        entered_key = st.text_input("Dealership License Key", placeholder="e.g. APACHE2026").strip().upper()
        if st.form_submit_button("Activate Dealership Session"):
            if entered_key in DEALER_ACCOUNTS:
                st.session_state.authenticated_dealer = entered_key
                st.query_params["key"] = entered_key
                st.rerun()
            else:
                st.error("Invalid key.")
    st.stop()

dealer_key = st.session_state.authenticated_dealer
dealer_info = DEALER_ACCOUNTS[dealer_key]

st.set_page_config(
    page_title=f"{dealer_info['name']} | Tow Match Pro",
    page_icon="rv-icon.png",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown(f"""
    <style>
    .dealer-header {{
        background: linear-gradient(135deg, {dealer_info['primary_color']}, {dealer_info['accent_color']});
        color: white; padding: 14px 18px; border-radius: 10px; margin-bottom: 14px;
    }}
    .unit-card {{
        background-color: #ffffff; border: 1px solid #e0e0e0; border-radius: 8px;
        padding: 12px; margin-bottom: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.04);
    }}
    .badge-on-my-lot {{ background-color: #1b5e20; color: #ffffff; padding: 3px 8px; border-radius: 4px; font-weight: 700; font-size: 0.75rem; text-transform: uppercase; }}
    .badge-other-lot {{ background-color: #455a64; color: #ffffff; padding: 3px 8px; border-radius: 4px; font-weight: 700; font-size: 0.75rem; text-transform: uppercase; }}
    .badge-pipeline {{ background-color: #e65100; color: #ffffff; padding: 3px 8px; border-radius: 4px; font-weight: 700; font-size: 0.75rem; text-transform: uppercase; }}
    
    .badge-new {{ background-color: #0d47a1; color: #ffffff; padding: 2px 6px; border-radius: 4px; font-weight: 700; font-size: 0.70rem; text-transform: uppercase; }}
    .badge-used {{ background-color: #5d4037; color: #ffffff; padding: 2px 6px; border-radius: 4px; font-weight: 700; font-size: 0.70rem; text-transform: uppercase; }}

    .safe-check {{ color: #1b5e20; font-weight: 700; font-size: 0.82rem; }}
    .marginal-check {{ color: #e65100; font-weight: 700; font-size: 0.82rem; }}
    .danger-check {{ color: #b71c1c; font-weight: 700; font-size: 0.82rem; }}
    </style>
""", unsafe_allow_html=True)

st.markdown(f"""
    <div class="dealer-header">
        <div style="font-size: 1.35rem; font-weight: 700;">{dealer_info['logo_icon']} {dealer_info['name']}</div>
        <div style="font-size: 0.85rem; opacity: 0.9;">{dealer_info['tagline']}</div>
    </div>
""", unsafe_allow_html=True)

if dealer_info.get("csv_file") and os.path.exists(dealer_info["csv_file"]):
    inv_df = pd.read_csv(dealer_info["csv_file"])
else:
    inv_df = pd.DataFrame(dealer_info["inventory"])

all_locations = sorted([loc for loc in inv_df["Location"].dropna().unique() if loc not in ["nan", "Unassigned / General"]])
default_idx = all_locations.index(dealer_info.get("default_lot")) if dealer_info.get("default_lot") in all_locations else 0

top_col1, top_col2 = st.columns([3, 1])
with top_col1:
    my_lot = st.selectbox("📍 My Selling Location (Active Lot):", all_locations, index=default_idx)
with top_col2:
    if st.button("Log Out"):
        st.session_state.authenticated_dealer = None
        st.query_params.clear()
        st.rerun()

# ---------------------------------------------------------
# Step 1: Tow Vehicle Specs
# ---------------------------------------------------------
st.write("---")
st.subheader("1. Tow Vehicle Specs")
entry_method = st.radio("Entry Method:", ["Door Placard (Fastest)", "Desk Lookup"], horizontal=True)

if entry_method == "Door Placard (Fastest)":
    c1, c2 = st.columns(2)
    with c1:
        payload_input = st.number_input("Sticker Payload (Yellow Tag)", min_value=600, max_value=8000, value=1650, step=50)
    with c2:
        gvwr_input = st.number_input("Truck GVWR (Safety Tag)", min_value=4000, max_value=16000, value=7100, step=100)
else:
    mk_col, md_col = st.columns(2)
    with mk_col:
        sel_make = st.selectbox("Make", list(TRUCK_FALLBACK_GUIDE.keys()))
    with md_col:
        sel_model = st.selectbox("Powertrain / Trim", list(TRUCK_FALLBACK_GUIDE[sel_make].keys()))
    spec = TRUCK_FALLBACK_GUIDE[sel_make][sel_model]
    payload_input, gvwr_input = spec["payload"], spec["gvwr"]

# ---------------------------------------------------------
# Step 2: Trip Loading & Passengers
# ---------------------------------------------------------
st.write("---")
st.subheader("2. Trip Loading & Passengers")
col_type, col_passengers = st.columns(2)
with col_type:
    rv_category = st.radio("Towable Style", ["Travel Trailer (Bumper Pull)", "Fifth Wheel"], horizontal=True)
with col_passengers:
    total_occupants = st.number_input("Occupants in Truck", min_value=1, max_value=6, value=2)

col_gear, col_hitch = st.columns(2)
with col_gear:
    bed_gear = st.number_input("Bed Cargo / Gear (lbs)", min_value=0, max_value=1500, value=150, step=50)
with col_hitch:
    hitch_wt = st.number_input("Hitch Hardware (lbs)", min_value=40, max_value=300, value=65 if "Travel Trailer" in rv_category else 175, step=5)

additional_passengers_weight = (total_occupants - 1) * 175
net_usable_payload = payload_input - additional_passengers_weight - bed_gear - hitch_wt

if "Fifth Wheel" in rv_category:
    pin_ratio, dry_buffer = 0.21, 1800
else:
    tongue_ratio, dry_buffer = 0.13, 1200

max_safe_trailer_gvwr = int(net_usable_payload / (pin_ratio if "Fifth Wheel" in rv_category else tongue_ratio))
max_recommended_dry_wt = max_safe_trailer_gvwr - dry_buffer

# ---------------------------------------------------------
# Step 3: Calculated Safe Limits
# ---------------------------------------------------------
st.write("---")
st.subheader("3. Calculated Safe Limits")
m1, m2, m3 = st.columns(3)
m1.metric("Available Hitch Payload", f"{net_usable_payload} lbs")
m2.metric("Max Safe RV GVWR", f"{max_safe_trailer_gvwr:,} lbs")
m3.metric("Max Target Dry Wt", f"~{max_recommended_dry_wt:,} lbs")

# ---------------------------------------------------------
# Step 4: Lot-First Matching & Filters
# ---------------------------------------------------------
st.write("---")
st.subheader("4. Matching Dealership Inventory")

target_type = "Travel Trailer" if "Travel Trailer" in rv_category else "Fifth Wheel"
filtered_inv = inv_df[inv_df["Type"] == target_type].copy()

def check_safety(row):
    try:
        gvwr = float(row["GVWR"])
        dry = float(row["DryWeight"])
    except (ValueError, TypeError):
        return "SAFE"

    if gvwr <= max_safe_trailer_gvwr:
        return "SAFE"
    elif dry <= max_recommended_dry_wt and gvwr <= (max_safe_trailer_gvwr * 1.07):
        return "MARGINAL"
    else:
        return "OVERWEIGHT"

filtered_inv["SafetyStatus"] = filtered_inv.apply(check_safety, axis=1)

# Proximity & Scope Filter
ctrl_col1, ctrl_col2 = st.columns([3, 2])
with ctrl_col1:
    inventory_scope = st.radio(
        "Inventory View:",
        [f"On My Lot ({my_lot})", "Include Other Locations & Inbound Pipeline"],
        horizontal=True
    )
with ctrl_col2:
    hide_overweight = st.checkbox("Hide Overweight Units", value=True)

# Condition Selector (Defaults to New) & Length Filters
filter_row1, filter_row2, filter_row3 = st.columns([2, 1.5, 1.5])
with filter_row1:
    condition_sel = st.radio("Condition:", ["New", "Used", "All"], index=0, horizontal=True)
with filter_row2:
    min_len_input = st.number_input("Min Length (ft)", min_value=0, max_value=45, value=0, step=1)
with filter_row3:
    max_len_input = st.number_input("Max Length (ft)", min_value=0, max_value=45, value=0, step=1)

# Apply Condition Filter
if condition_sel != "All" and "Condition" in filtered_inv.columns:
    filtered_inv = filtered_inv[filtered_inv["Condition"] == condition_sel]

# Apply Overweight Filter
if hide_overweight:
    filtered_inv = filtered_inv[filtered_inv["SafetyStatus"] != "OVERWEIGHT"]

# Apply Length Filters
if min_len_input > 0 and "Length" in filtered_inv.columns:
    filtered_inv = filtered_inv[filtered_inv["Length"] >= min_len_input]

if max_len_input > 0 and "Length" in filtered_inv.columns:
    filtered_inv = filtered_inv[filtered_inv["Length"] <= max_len_input]

# Apply Lot Proximity Filter
if inventory_scope.startswith("On My Lot"):
    filtered_inv = filtered_inv[(filtered_inv["Location"] == my_lot) & (filtered_inv["Status"] == "On Lot")]
    st.info(f"Showing **{condition_sel}** units physically parked on the gravel right now at {my_lot}.")
else:
    st.warning(f"Showing **{condition_sel}** units across all locations, sister stores, and incoming factory orders.")

st.caption(f"Found **{len(filtered_inv)}** matching units within safe towing specifications.")

if filtered_inv.empty:
    st.error(f"No {condition_sel.lower()} units on the {my_lot} lot meet these exact specs. Try switching Condition to 'All' or expand inventory view.")
else:
    for _, unit in filtered_inv.iterrows():
        is_here_now = (unit["Location"] == my_lot and unit["Status"] == "On Lot")
        is_incoming = (unit["Status"] != "On Lot")

        if is_here_now:
            lot_badge = f'<span class="badge-on-my-lot">● ON THIS LOT ({unit["Location"]})</span>'
        elif is_incoming:
            lot_badge = f'<span class="badge-pipeline">✈ INCOMING TO {unit["Location"]}</span>'
        else:
            lot_badge = f'<span class="badge-other-lot">⇄ TRANSFER FROM {unit["Location"]}</span>'

        unit_cond = str(unit.get("Condition", "New"))
        cond_badge = '<span class="badge-new">NEW</span>' if unit_cond == "New" else '<span class="badge-used">USED</span>'

        if unit["SafetyStatus"] == "SAFE":
            safety_html = '<span class="safe-check">✓ SAFE TO TOW</span>'
        elif unit["SafetyStatus"] == "MARGINAL":
            safety_html = '<span class="marginal-check">⚠️ MARGINAL (PACK LIGHT)</span>'
        else:
            safety_html = '<span class="danger-check">✕ OVERWEIGHT FOR TRUCK</span>'

        img_src = str(unit.get("Image", ""))
        if not img_src or img_src == "nan":
            img_src = "https://via.placeholder.com/300x200?text=Apache+RV"

        length_display = f"{int(unit['Length'])} ft" if ("Length" in unit and pd.notna(unit["Length"])) else "N/A"

        st.markdown(f"""
            <div class="unit-card">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 8px;">
                    <div>{lot_badge} &nbsp; {cond_badge} &nbsp; <span style="font-size:0.8rem; color:#666;">Stock #{unit['Stock']}</span></div>
                    <div>{safety_html}</div>
                </div>
                <div style="display: flex; gap: 14px; align-items: flex-start;">
                    <img src="{img_src}" style="width: 110px; height: 75px; object-fit: cover; border-radius: 6px; flex-shrink: 0; box-shadow: 0 1px 3px rgba(0,0,0,0.15);" />
                    <div style="flex-grow: 1;">
                        <div style="font-size: 1.05rem; font-weight:700; color:#222; margin-bottom: 4px;">
                            {unit['Year']} {unit['Model']}
                        </div>
                        <div style="display:flex; justify-content:space-between; font-size:0.85rem; color:#444;">
                            <span>Length: <b>{length_display}</b></span>
                            <span>Dry: <b>{int(unit['DryWeight']):,} lbs</b></span>
                            <span>GVWR: <b>{int(unit['GVWR']):,} lbs</b></span>
                        </div>
                        <div style="margin-top: 4px; font-size: 0.85rem; color:#1b5e20; font-weight: 600;">
                            Price: {unit['Price']}
                        </div>
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)
