import streamlit as st
import pandas as pd
from geopy.distance import geodesic
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
import json
import streamlit.components.v1 as components

st.set_page_config(page_title="Housing Routing & Property Map", layout="wide")

# -------------------- CONSTANTS --------------------
OFFICE_LOCATION = (41.6586, -91.5302)
OFFICE_ADDRESS_STR = "322 E 2nd St, Iowa City, IA"


# -------------------- UTILS --------------------
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


def get_route(manager, routing, solution):
    index = routing.Start(0)
    route = []
    while not routing.IsEnd(index):
        route.append(manager.IndexToNode(index))
        index = solution.Value(routing.NextVar(index))
    route.append(manager.IndexToNode(index))
    return route


# -------------------- PROPERTY INFORMATION MAP --------------------
def render_property_map(property_df: pd.DataFrame):
    """Leaflet property information map using the uploaded CSV."""
    if property_df.empty:
        st.info("No property data to display.")
        return

    records = []
    for _, row in property_df.iterrows():
        lat = row.get("Latitude")
        lng = row.get("Longitude")
        if pd.isna(lat) or pd.isna(lng):
            continue

        rec = {
            # Prefer Name, fall back to Address
            "name": str(row.get("Name", row.get("Address", ""))),
            "lat": float(lat),
            "lng": float(lng),
            "beds": row.get("NumberofBeds"),
            "baths": row.get("NumberofBaths"),
            "loan1": row.get("Loan1"),
            "loan1_interest": row.get("Loan1inter", row.get("Loan1Inter")),
            "loan1_pmt": row.get("Loan1pmt"),
            "loan2": row.get("Loan2") or row.get("Loan2 "),
            "loan2_interest": row.get("Loan2inter", row.get("Loan2Inter")),
            "loan2_pmt": row.get("Loan2pmt"),
            "loan3": row.get("Loan3"),
            "loan3_interest": row.get("Loan3inter", row.get("Loan3Inter")),
            "loan3_pmt": row.get("Loan3pmt"),
            "loan4": row.get("Loan4"),
            "loan4_interest": row.get("Loan4inter", row.get("Loan4Inter")),
            "loan4_pmt": row.get("Loan4pmt"),
            "loan5": row.get("Loan5"),
            "loan5_interest": row.get("Loan5inter", row.get("Loan5Inter")),
            "loan5_pmt": row.get("Loan5pmt"),
            "compliance": row.get("Complianceexpiration"),
        }
        records.append(rec)

    if not records:
        st.info("No properties with valid coordinates.")
        return

    center_lat = sum(r["lat"] for r in records) / len(records)
    center_lng = sum(r["lng"] for r in records) / len(records)
    data_json = json.dumps(records)

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8" />
      <title>Property Map</title>
      <meta name="viewport" content="width=device-width, initial-scale=1.0">

      <link
        rel="stylesheet"
        href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
        crossorigin=""
      />
      <style>
        #map {{
          width: 100%;
          height: 500px;
        }}

        .popup-panel {{
          min-width: 260px;
          max-width: 320px;
          max-height: 320px;
          overflow-y: auto;
          font-size: 12px;
          font-family: Arial, sans-serif;
        }}
        .popup-table {{
          width: 100%;
          border-collapse: collapse;
          background: white;
        }}
        .popup-table th,
        .popup-table td {{
          padding: 4px 6px;
          border: 1px solid #000;
          vertical-align: top;
        }}
        .popup-section-header th {{
          background: #b30000 !important;
          color: white;
          font-weight: 600;
          text-align: center;
          padding: 4px 0;
          font-size: 14px;
        }}
        .popup-table th {{
          background: #ffd6d6;
          color: #000;
          font-weight: 600;
          width: 40%;
        }}
        .popup-table td {{
          background: #ffe6e6;
          color: #000;
        }}

        .search-control {{
          position: absolute;
          top: 10px;
          left: 10px;
          z-index: 1000;
          background: white;
          padding: 6px 8px;
          border-radius: 4px;
          box-shadow: 0 0 4px rgba(0,0,0,0.3);
          font-size: 12px;
        }}
        .search-control input {{
          width: 160px;
          padding: 2px 4px;
          margin-bottom: 4px;
          border: 1px solid #ccc;
          border-radius: 3px;
        }}
        .search-control button {{
          width: 100%;
          padding: 2px 4px;
          border: 1px solid #b30000;
          background: #b30000;
          color: #fff;
          border-radius: 3px;
          cursor: pointer;
        }}
        .search-control button:hover {{
          background: #7a0000;
        }}
      </style>
    </head>
    <body>
      <div id="map"></div>

      <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" crossorigin=""></script>
      <script>
        const properties = {data_json};

        var map = L.map('map').setView([{center_lat}, {center_lng}], 12);
        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
          maxZoom: 19,
          attribution: '&copy; OpenStreetMap contributors'
        }}).addTo(map);

        const bounds = [];
        const propertyMarkers = [];

        properties.forEach(p => {{
          if (isNaN(p.lat) || isNaN(p.lng)) return;

          const popupHtml = `
            <div class="popup-panel">
              <table class="popup-table">
                <tr class="popup-section-header">
                  <th colspan="2">${{p.name || "Property Information"}}</th>
                </tr>
                <tr>
                  <th>Beds</th>
                  <td>${{p.beds || "N/A"}}</td>
                </tr>
                <tr>
                  <th>Baths</th>
                  <td>${{p.baths || "N/A"}}</td>
                </tr>

                <tr class="popup-section-header">
                  <th colspan="2">Loans</th>
                </tr>
                <tr><th>Loan 1 amount</th><td>${{p.loan1 || "N/A"}}</td></tr>
                <tr><th>Loan 1 interest</th><td>${{p.loan1_interest || "N/A"}}</td></tr>
                <tr><th>Loan 1 payment</th><td>${{p.loan1_pmt || "N/A"}}</td></tr>

                <tr><th>Loan 2 amount</th><td>${{p.loan2 || "N/A"}}</td></tr>
                <tr><th>Loan 2 interest</th><td>${{p.loan2_interest || "N/A"}}</td></tr>
                <tr><th>Loan 2 payment</th><td>${{p.loan2_pmt || "N/A"}}</td></tr>

                <tr><th>Loan 3 amount</th><td>${{p.loan3 || "N/A"}}</td></tr>
                <tr><th>Loan 3 interest</th><td>${{p.loan3_interest || "N/A"}}</td></tr>
                <tr><th>Loan 3 payment</th><td>${{p.loan3_pmt || "N/A"}}</td></tr>

                <tr><th>Loan 4 amount</th><td>${{p.loan4 || "N/A"}}</td></tr>
                <tr><th>Loan 4 interest</th><td>${{p.loan4_interest || "N/A"}}</td></tr>
                <tr><th>Loan 4 payment</th><td>${{p.loan4_pmt || "N/A"}}</td></tr>

                <tr><th>Loan 5 amount</th><td>${{p.loan5 || "N/A"}}</td></tr>
                <tr><th>Loan 5 interest</th><td>${{p.loan5_interest || "N/A"}}</td></tr>
                <tr><th>Loan 5 payment</th><td>${{p.loan5_pmt || "N/A"}}</td></tr>

                <tr class="popup-section-header">
                  <th colspan="2">Compliance</th>
                </tr>
                <tr>
                  <th>Expiration</th>
                  <td>${{p.compliance || "N/A"}}</td>
                </tr>

                <tr class="popup-section-header">
                  <th colspan="2">Coordinates</th>
                </tr>
                <tr>
                  <th>Lat / Lng</th>
                  <td>${{p.lat.toFixed(6)}}, ${{p.lng.toFixed(6)}}</td>
                </tr>
              </table>
            </div>
          `;

          const marker = L.marker([p.lat, p.lng]).addTo(map);
          marker.bindPopup(popupHtml);
          bounds.push([p.lat, p.lng]);
          propertyMarkers.push({{ name: (p.name || "").toString(), marker: marker }});
        }});

        if (bounds.length > 0) {{
          map.fitBounds(bounds);
        }}

        // Search control
        const searchDiv = L.DomUtil.create('div', 'search-control');
        searchDiv.innerHTML = `
          <div><b>Search property</b></div>
          <input type="text" placeholder="Name or address" />
          <button type="button">Search</button>
        `;
        const searchControl = L.control({{position: 'topleft'}});
        searchControl.onAdd = function() {{ return searchDiv; }};
        searchControl.addTo(map);

        const input = searchDiv.querySelector('input');
        const button = searchDiv.querySelector('button');

        L.DomEvent.disableClickPropagation(searchDiv);

        function doSearch() {{
          const q = input.value.trim().toLowerCase();
          if (!q) return;
          const match = propertyMarkers.find(p =>
            p.name && p.name.toLowerCase().includes(q)
          );
          if (match) {{
            const latlng = match.marker.getLatLng();
            map.setView(latlng, 17);
            match.marker.openPopup();
          }} else {{
            alert("No property found for: " + input.value);
          }}
        }}

        button.addEventListener('click', doSearch);
        input.addEventListener('keydown', function(e) {{
          if (e.key === 'Enter') doSearch();
        }});
      </script>
    </body>
    </html>
    """

    components.html(html, height=520)


# -------------------- SHARED UPLOADER --------------------
st.title("🏘 Housing Tools")

st.markdown("Upload a single CSV and use it for **both** the route optimizer and the property info map.")

uploaded_file = st.file_uploader("Upload housing CSV", type=["csv"])
df_raw = pd.read_csv(uploaded_file) if uploaded_file else None

# -------------------- TABS --------------------
route_tab, property_tab = st.tabs(["🚚 Route Optimizer", "🏠 Property Information"])


# -------------------- ROUTE TAB --------------------
with route_tab:
    st.subheader("📦 Housing Visit Route Optimizer (Amazon-style)")

    st.markdown("""
CSV must have at least:
- **Latitude**
- **Longitude**

If it has **Address** or **Name**, that will be shown in the results.
""")

    if df_raw is None:
        st.info("Upload a CSV above to run the route optimizer.")
    else:
        df = df_raw.copy()

        # If there's no 'Address' but there is 'Name', treat Name as Address for display
        if "Address" not in df.columns and "Name" in df.columns:
            df = df.rename(columns={"Name": "Address"})

        missing_latlng = [c for c in ["Latitude", "Longitude"] if c not in df.columns]
        if missing_latlng:
            st.error(f"Missing required column(s): {missing_latlng}. Need Latitude and Longitude.")
        else:
            # Keep only rows with valid coordinates
            df = df.dropna(subset=["Latitude", "Longitude"]).copy()

            # Build locations list matching index: 0=office, then df rows
            locations = [OFFICE_LOCATION] + list(zip(df["Latitude"], df["Longitude"]))
            distance_matrix = compute_distance_matrix(locations)

            manager = pywrapcp.RoutingIndexManager(len(locations), 1, 0)  # depot=0 (office)
            routing = pywrapcp.RoutingModel(manager)

            def distance_callback(from_index, to_index):
                from_node = manager.IndexToNode(from_index)
                to_node = manager.IndexToNode(to_index)
                return distance_matrix[from_node][to_node]

            transit_callback_index = routing.RegisterTransitCallback(distance_callback)
            routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

            try:
                routing.SetStartEnd(0, 0)
            except Exception:
                pass  # older OR-Tools compatibility

            search_params = pywrapcp.DefaultRoutingSearchParameters()
            search_params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC

            solution = routing.SolveWithParameters(search_params)

            if solution:
                route = get_route(manager, routing, solution)

                # route is a list of node indices in 'locations'
                # 0 is office, 1..N are df rows (shifted by -1 to align with df)
                stop_sequence = route[1:-1]  # exclude office at start and end
                df_ordered = df.iloc[[i - 1 for i in stop_sequence]].copy()
                df_ordered.insert(0, "StopOrder", range(1, len(df_ordered) + 1))

                st.success("✅ Optimized Route Generated")

                # Choose which address-like column to display
                address_col = None
                for candidate in ["Address", "Name", "address"]:
                    if candidate in df_ordered.columns:
                        address_col = candidate
                        break

                cols_to_show = ["StopOrder"]
                if address_col:
                    cols_to_show.append(address_col)
                for c in ["Latitude", "Longitude"]:
                    if c in df_ordered.columns:
                        cols_to_show.append(c)

                st.dataframe(df_ordered[cols_to_show])

                # ---- Google Maps link using COORDINATES ----
                MAX_WAYPOINTS = 8
                df_limited = df_ordered.head(MAX_WAYPOINTS)

                waypoints = "|".join(
                    [f"{row['Latitude']},{row['Longitude']}" for _, row in df_limited.iterrows()]
                )

                origin_coord = f"{OFFICE_LOCATION[0]},{OFFICE_LOCATION[1]}"
                dest_coord = origin_coord

                base = "https://www.google.com/maps/dir/?api=1"
                maps_url = (
                    f"{base}&origin={origin_coord}&destination={dest_coord}"
                    f"&waypoints={waypoints}&travelmode=driving"
                )

                st.markdown(f"[🗺️ Open in Google Maps (first {MAX_WAYPOINTS} stops)]({maps_url})")

                if len(df_ordered) > MAX_WAYPOINTS:
                    st.info(
                        f"Google Maps URL limited to ~{MAX_WAYPOINTS} waypoints; "
                        f"exported CSV contains all {len(df_ordered)} stops."
                    )

                st.download_button(
                    "📥 Download Full Optimized Route CSV",
                    df_ordered.to_csv(index=False),
                    file_name="optimized_route.csv"
                )
            else:
                st.error("❌ Could not solve routing problem.")


# -------------------- PROPERTY TAB --------------------
with property_tab:
    st.subheader("🏠 Property Information Map")

    if df_raw is None:
        st.info("Upload the property CSV above to see the map.")
    else:
        st.write("Preview of uploaded data:")
        st.dataframe(df_raw.head())
        render_property_map(df_raw)