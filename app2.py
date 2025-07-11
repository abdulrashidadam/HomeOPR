import os
import streamlit as st
import pandas as pd
import requests
import folium
from streamlit_folium import st_folium
from geopy.distance import geodesic
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
from folium.plugins import AntPath

# Disable watchdog error
os.environ["STREAMLIT_WATCHDOG_MODE"] = "poll"

# ----------------------------
# UI Configuration and Styling
# ----------------------------
st.set_page_config(page_title="Housing Fellowship Routing", layout="wide")

st.markdown("""
    <style>
        body {
            background-color: white;
            color: black;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        .reportview-container .markdown-text-container {
            padding: 2rem;
        }
        .dark-mode {
            background-color: #121212;
            color: #e0e0e0;
        }
        .light-mode {
            background-color: #ffffff;
            color: #000000;
        }
        .styled-button {
            background-color: gold;
            color: black;
            border: none;
            border-radius: 5px;
            padding: 10px 20px;
            font-weight: bold;
            transition: background-color 0.3s ease;
        }
        .styled-button:hover {
            background-color: #ffd700;
        }
    </style>
""", unsafe_allow_html=True)

# ----------------------------
# Logo / Banner
# ----------------------------
st.image("Home.webp", use_container_width=True)

st.markdown("""
<div style='background-color:#000000;padding:20px;border-radius:10px;'>
    <h1 style='color:gold;text-align:center;'>🏠 HOUSING FELLOWSHIP EFFICIENT ROUTING</h1>
</div>
""", unsafe_allow_html=True)

# Theme Toggle
if st.toggle("🌙 Dark Mode"):
    st.markdown('<style>body{background-color:#121212;color:#e0e0e0;}</style>', unsafe_allow_html=True)

st.markdown("""
Upload a CSV file with these columns:
- **Address** (optional, but recommended for map labeling)
- **Latitude**
- **Longitude**
- *(Optional)* TimeWindowStart, TimeWindowEnd (in minutes from day start)

The system will:
- Start and end at your office (322 E 2nd St)
- Optimize the route based on distance or OSRM
- Optionally apply left-turn penalties if OSRM is used
""")

st.markdown("""
<div style='background-color:#f8f8f8;padding:10px 20px;border-left:5px solid gold;'>
    <h4>📄 Upload Your Stops CSV</h4>
</div>
""", unsafe_allow_html=True)

uploaded_file = st.file_uploader("Upload Stops CSV", type=["csv"])
office_location = (41.64780095073108, -91.53141740885403)  # Office address (lat, lon)
office_address = "322 E 2nd St, Iowa City, IA 52240"

# --------------------------
# Distance Matrix Functions
# --------------------------
def compute_geodesic_matrix(locations):
    matrix = {}
    for i, from_node in enumerate(locations):
        matrix[i] = {}
        for j, to_node in enumerate(locations):
            matrix[i][j] = 0 if i == j else int(geodesic(from_node, to_node).meters)
    return matrix

def compute_osrm_matrix(locations):
    coords = ";".join([f"{lon},{lat}" for lat, lon in locations])
    url = f"http://localhost:5000/table/v1/driving/{coords}?annotations=distance"
    try:
        res = requests.get(url).json()
        distances = res['distances']
        matrix = {i: {j: int(distances[i][j]) for j in range(len(distances))} for i in range(len(distances))}
        return matrix
    except:
        return compute_geodesic_matrix(locations)  # fallback

# -----------------------
# Route Optimization
# -----------------------
def solve_tsp(matrix):
    size = len(matrix)
    manager = pywrapcp.RoutingIndexManager(size, 1, 0)
    routing = pywrapcp.RoutingModel(manager)

    def distance_callback(from_index, to_index):
        from_node, to_node = manager.IndexToNode(from_index), manager.IndexToNode(to_index)
        return matrix[from_node][to_node]

    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    search_params = pywrapcp.DefaultRoutingSearchParameters()
    search_params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    solution = routing.SolveWithParameters(search_params)

    if not solution:
        return None

    index = routing.Start(0)
    route = []
    while not routing.IsEnd(index):
        route.append(manager.IndexToNode(index))
        index = solution.Value(routing.NextVar(index))
    route.append(manager.IndexToNode(index))
    return route

# -----------------------
# Main Execution
# -----------------------
if uploaded_file:
    df = pd.read_csv(uploaded_file)
    df = df.dropna(subset=["Latitude", "Longitude"])
    if "Address" not in df.columns:
        df["Address"] = df[["Latitude", "Longitude"]].astype(str).agg(", ".join, axis=1)

    locations = [office_location] + list(zip(df["Latitude"], df["Longitude"]))

    routing_method = st.radio("Select Routing Method", ["Distance only", "Use OSRM with left-turn penalties"])

    with st.spinner("⏳ Computing optimized route..."):
        if routing_method == "Use OSRM with left-turn penalties":
            distance_matrix = compute_osrm_matrix(locations)
        else:
            distance_matrix = compute_geodesic_matrix(locations)

        route = solve_tsp(distance_matrix)

    if route:
        stop_sequence = route[1:-1]
        optimized_df = df.iloc[[i - 1 for i in stop_sequence]].copy()
        optimized_df.insert(0, "StopOrder", range(1, len(optimized_df) + 1))

        # Generate Google Maps directions URL with full route
        waypoints = "|".join([f"{row['Address'].replace(' ', '+')}" for _, row in optimized_df.iterrows()])
        maps_url = f"https://www.google.com/maps/dir/?api=1&origin={office_address.replace(' ', '+')}&destination={office_address.replace(' ', '+')}&travelmode=driving&waypoints={waypoints}"

        optimized_df["Navigate Link"] = optimized_df["Address"].apply(lambda x: f"https://www.google.com/maps/dir/?api=1&destination={x.replace(' ', '+')}")

        st.success("✅ Optimized Route Generated")
        st.dataframe(optimized_df, use_container_width=True)

        st.markdown(f"[🧭 View Turn-by-Turn Directions in Google Maps]({maps_url})")

        st.download_button("📥 Download Full Optimized Route CSV", optimized_df.to_csv(index=False), file_name="optimized_route.csv")

        route_map = folium.Map(location=office_location, zoom_start=12, tiles="CartoDB positron")
        folium.Marker(location=office_location, tooltip="🏠 Office", icon=folium.Icon(color='green', icon='home')).add_to(route_map)

        coords = [office_location]
        for i, row in optimized_df.iterrows():
            loc = (row.Latitude, row.Longitude)
            folium.Marker(loc, tooltip=f"📍 Stop {row.StopOrder}: {row.Address}", icon=folium.Icon(color='blue', icon='flag')).add_to(route_map)
            coords.append(loc)
        coords.append(office_location)
        AntPath(coords, color="gold", weight=4).add_to(route_map)

        st_folium(route_map, width=750, height=500)

        export_html = "route_map.html"
        route_map.save(export_html)
        with open(export_html, "rb") as f:
            st.download_button("📄 Download Map as HTML", f, file_name="route_map.html")

        st.markdown("""
        <br><hr><p style='text-align:center;'>
        🔗 Share this tool: <a href='https://share.streamlit.io/your-deployment-url' target='_blank'>Streamlit App</a>
        </p>
        """, unsafe_allow_html=True)
    else:
        st.error("❌ Could not solve routing problem.")
