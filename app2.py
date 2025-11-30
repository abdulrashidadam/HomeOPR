import streamlit as st
import pandas as pd
import numpy as np
from geopy.distance import geodesic
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp

st.title("📦 Housing Visit Route Optimizer (Amazon-style)")

st.markdown("""
Upload a CSV file with these columns:
- **Address**
- **Latitude**
- **Longitude**
- *(Optional)* `TimeWindowStart`, `TimeWindowEnd` (in minutes from day start)

The system will:
- Start and end at your office (322 E 2nd St)
- Optimize the route based on distance
""")

uploaded_file = st.file_uploader("Upload Stops CSV", type=["csv"])

# Office (lat, lon)
office_location = (41.6586, -91.5302)
office_address_str = "322+E+2nd+St+Iowa+City+IA"  # only used if you prefer address origin/destination

def compute_distance_matrix(locations):
    matrix = {}
    for i, from_node in enumerate(locations):
        matrix[i] = {}
        for j, to_node in enumerate(locations):
            if i == j:
                matrix[i][j] = 0
            else:
                matrix[i][j] = int(geodesic(from_node, to_node).meters)
    return matrix

if uploaded_file:
    df = pd.read_csv(uploaded_file)

    # Keep only rows with valid coordinates
    df = df.dropna(subset=["Latitude", "Longitude"]).copy()

    # Build locations list matching index: 0=office, then df rows
    locations = [office_location] + list(zip(df["Latitude"], df["Longitude"]))
    distance_matrix = compute_distance_matrix(locations)

    manager = pywrapcp.RoutingIndexManager(len(locations), 1, 0)  # depot=0 (office)
    routing = pywrapcp.RoutingModel(manager)

    def distance_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return distance_matrix[from_node][to_node]

    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    # (Optional) explicitly set same start & end at depot 0
    try:
        routing.SetStartEnd(0, 0)
    except Exception:
        pass  # for older OR-Tools, depot is already start=end by default for 1 vehicle

    search_params = pywrapcp.DefaultRoutingSearchParameters()
    search_params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC

    solution = routing.SolveWithParameters(search_params)

    def get_route(manager, routing, solution):
        index = routing.Start(0)
        route = []
        while not routing.IsEnd(index):
            route.append(manager.IndexToNode(index))
            index = solution.Value(routing.NextVar(index))
        route.append(manager.IndexToNode(index))
        return route

    if solution:
        route = get_route(manager, routing, solution)

        # route is a list of node indices in 'locations'
        # 0 is office, 1..N are df rows (shifted by -1 to align with df)
        stop_sequence = route[1:-1]  # exclude office at start and end
        df_ordered = df.iloc[[i - 1 for i in stop_sequence]].copy()
        df_ordered.insert(0, "StopOrder", range(1, len(df_ordered) + 1))

        st.success("✅ Optimized Route Generated")
        st.dataframe(df_ordered[["StopOrder", "Address", "Latitude", "Longitude"]])

        # ---- Google Maps link using COORDINATES (fixes “wrong addresses” issue) ----
        # Google consumer URL supports about 10 total locations (origin+destination+~8 waypoints).
        MAX_WAYPOINTS = 8
        df_limited = df_ordered.head(MAX_WAYPOINTS)

        # waypoints as "lat,lon" pairs
        waypoints = "|".join([f"{row['Latitude']},{row['Longitude']}" for _, row in df_limited.iterrows()])

        # you can also set origin/destination as coordinates:
        origin_coord = f"{office_location[0]},{office_location[1]}"
        dest_coord = origin_coord

        base = "https://www.google.com/maps/dir/?api=1"
        maps_url = f"{base}&origin={origin_coord}&destination={dest_coord}&waypoints={waypoints}&travelmode=driving"

        st.markdown(f"[🗺️ Open in Google Maps (first {MAX_WAYPOINTS} stops)]({maps_url})")

        if len(df_ordered) > MAX_WAYPOINTS:
            st.info(f"Google Maps URL limited to ~{MAX_WAYPOINTS} waypoints; exported CSV contains all {len(df_ordered)} stops.")

        # Export full optimized list
        st.download_button("📥 Download Full Optimized Route CSV",
                           df_ordered.to_csv(index=False),
                           file_name="optimized_route.csv")
    else:
        st.error("❌ Could not solve routing problem.")