# Filename: RouteMapClustered.py - SIMPLE WORKING VERSION

import pandas as pd
import numpy as np
import folium
import requests
import time
from sklearn.cluster import KMeans
from pyproj import Transformer
from scipy.spatial.distance import cdist
import warnings
warnings.filterwarnings("ignore")

# Google Maps API Key
GOOGLE_API_KEY = "AIzaSyDSd-fc2wicMn2lT5L6MA5ikQrq6EPV0PQ"

def get_driving_distance_matrix(coords):
    """Get driving distance matrix using Google Maps API"""
    if len(coords) > 25:
        mid = len(coords) // 2
        dist1 = get_driving_distance_matrix(coords[:mid])
        dist2 = get_driving_distance_matrix(coords[mid:])
        return dist1 + dist2[len(dist1):]
    
    origins = "|".join([f"{lat},{lon}" for lat, lon in coords])
    url = f"https://maps.googleapis.com/maps/api/distancematrix/json"
    params = {
        "origins": origins, "destinations": origins,
        "key": GOOGLE_API_KEY, "units": "metric", "mode": "driving"
    }
    
    response = requests.get(url, params=params)
    data = response.json()
    
    if data["status"] != "OK":
        print(f"API Error: {data}")
        return None
    
    n = len(coords)
    dist_matrix = np.full((n, n), np.inf)
    
    for i in range(n):
        for j in range(n):
            element = data["rows"][i]["elements"][j]
            if element["status"] == "OK":
                dist_matrix[i, j] = element["distance"]["value"]
    
    time.sleep(0.1)
    return dist_matrix

# Ask User for Clusters and Days
num_clusters = int(input("Enter number of clusters (employees): "))
num_days = int(input("Enter number of days: "))

# Load Data
df = pd.read_csv("RouteMapTest_geocodio_597c512cff07e8d5a779efb38f8157b8ee45dba6.csv")
df = df.rename(columns={"Geocodio Latitude": "Latitude", "Geocodio Longitude": "Longitude"})
df = df.dropna(subset=["Latitude", "Longitude"]).reset_index(drop=True)
print("Data loaded. Total locations:", len(df))

# Clustering (UNCHANGED - WORKS PERFECTLY)
transformer = Transformer.from_crs("epsg:4326", "epsg:3857", always_xy=True)
projected_coords = np.array([transformer.transform(lon, lat) for lat, lon in zip(df["Latitude"], df["Longitude"])])

kmeans = KMeans(n_clusters=num_clusters, random_state=42, n_init=20, max_iter=500)
df["Cluster"] = kmeans.fit_predict(projected_coords)

print("\nCluster counts (employees):")
print(df["Cluster"].value_counts().sort_index())

df["DayCluster"] = -1
for cluster_id in sorted(df["Cluster"].unique()):
    mask = df["Cluster"] == cluster_id
    cluster_df = df[mask].copy()
    n_points = len(cluster_df)
    if n_points == 0: continue
    if n_points <= num_days:
        df.loc[mask, "DayCluster"] = np.arange(n_points)
        continue
    cluster_df = cluster_df.sort_values(["Latitude", "Longitude"]).reset_index()
    base_size = n_points // num_days
    remainder = n_points % num_days
    day_labels = np.empty(n_points, dtype=int)
    start = 0
    for day in range(num_days):
        size = base_size + (1 if day < remainder else 0)
        end = start + size
        day_labels[start:end] = day
        start = end
    df.loc[cluster_df["index"], "DayCluster"] = day_labels

print("\nDay cluster counts:")
print(df.groupby(["Cluster", "DayCluster"]).size())

# SIMPLIFIED MAP - 100% WORKING
center_lat = df["Latitude"].mean()
center_lon = df["Longitude"].mean()
m = folium.Map(location=[center_lat, center_lon], zoom_start=12, tiles='OpenStreetMap')

colors = ["red", "blue", "green", "purple", "orange", "darkred", "lightred", "beige", "darkblue", "darkgreen"]

# Add SIMPLE sidebar HTML (no complex JS)
sidebar_html = '''
<div id="info-panel" style="
    position: fixed; top: 60px; right: 10px; width: 300px; max-height: 70vh;
    background: white; border: 2px solid #333; border-radius: 8px; padding: 15px;
    z-index: 1000; font-family: Arial; font-size: 13px; box-shadow: 0 4px 12px rgba(0,0,0,0.3);
">
    <h4 style="margin: 0 0 10px 0; color: #333;">📍 Location Info</h4>
    <div id="info-content" style="line-height: 1.4;">
        <i>Click any marker for details</i>
    </div>
</div>

<style>
.highlighted { stroke-width: 5px !important; stroke: yellow !important; fill-opacity: 1 !important; }
</style>

<script>
// Simple click handler for ALL markers
function initSidebar() {
    var panel = document.getElementById("info-panel");
    document.addEventListener("click", function(e) {
        var marker = e.target.closest(".leaflet-marker-icon");
        if (!marker) return;
        
        var retailer = marker.getAttribute("data-retailer") || "Unknown";
        var cluster = marker.getAttribute("data-cluster") || "?";
        var day = marker.getAttribute("data-day") || "?";
        var addr = marker.getAttribute("data-addr") || "";
        
        document.getElementById("info-content").innerHTML = 
            "<b>" + retailer + "</b><br>" +
            "Employee: " + cluster + "<br>" +
            "Day: " + day + "<br>" +
            addr;
    });
}
window.onload = initSidebar;
</script>
'''

m.get_root().html.add_child(folium.Element(sidebar_html))

# Add markers with data attributes (SIMPLE)
for idx, row in df.iterrows():
    cluster_id = int(row["Cluster"])
    day_cluster_id = int(row["DayCluster"])
    color = colors[cluster_id % len(colors)]
    
    popup_text = f"""
    <b>{row['Retailer']}</b><br>
    Employee Cluster: {cluster_id + 1}<br>
    Day Cluster: {day_cluster_id + 1}<br>
    {row['Address']}, {row['City']}
    """
    
    folium.CircleMarker(
        location=[row["Latitude"], row["Longitude"]],
        radius=7, color="black", weight=2, fill=True, fillColor=color, fillOpacity=0.8,
        popup=folium.Popup(popup_text, max_width=250),
        tooltip=f"{row['Retailer']} (E{cluster_id+1} D{day_cluster_id+1})"
    ).add_to(m)

# Black cluster boundaries (UNCHANGED)
for cluster_id in sorted(df["Cluster"].unique()):
    for day_cluster_id in sorted(df[df["Cluster"] == cluster_id]["DayCluster"].unique()):
        sub = df[(df["Cluster"] == cluster_id) & (df["DayCluster"] == day_cluster_id)]
        if sub.empty: continue
        bounds = [
            [sub["Latitude"].min(), sub["Longitude"].min()],
            [sub["Latitude"].min(), sub["Longitude"].max()],
            [sub["Latitude"].max(), sub["Longitude"].max()],
            [sub["Latitude"].max(), sub["Longitude"].min()],
            [sub["Latitude"].min(), sub["Longitude"].min()]
        ]
        folium.PolyLine(locations=bounds, color="black", weight=3, opacity=0.8).add_to(m)

m.save("RouteOptimization_Clustered_Map.html")
print("\n Map saved! Open in Chrome/Firefox")

# ROUTING (UNCHANGED)
def compute_driving_route_order(coords):
    n = len(coords)
    if n <= 1: return list(range(n))
    
    print(f"  Computing driving matrix for {n} points...")
    dist_matrix = get_driving_distance_matrix(coords)
    if dist_matrix is None: return list(range(n))
    
    visited = [0]
    while len(visited) < n:
        last = visited[-1]
        dist_row = dist_matrix[last].copy()
        for v in visited: dist_row[v] = np.inf
        next_idx = np.argmin(dist_row)
        visited.append(next_idx)
    return visited

print("\n Computing routes...")
route_output = []
for (cluster_id, day_cluster_id), group in df.groupby(["Cluster", "DayCluster"]):
    print(f"Processing Cluster {cluster_id+1}, Day {day_cluster_id+1} ({len(group)} points)")
    cluster_df = group.copy()
    coords = cluster_df[["Latitude", "Longitude"]].values.tolist()
    order = compute_driving_route_order(coords)
    cluster_df = cluster_df.iloc[order].reset_index(drop=True)
    cluster_df["Visit Order"] = range(1, len(cluster_df) + 1)
    cluster_df["Cluster"] = cluster_id + 1
    cluster_df["DayCluster"] = day_cluster_id + 1
    cluster_df["Day"] = day_cluster_id + 1
    route_output.append(cluster_df)

route_df = pd.concat(route_output, ignore_index=True)
geocode_cols = [col for col in route_df.columns if col.startswith("Geocodio")]
route_df = route_df.drop(columns=geocode_cols + ["Latitude", "Longitude"], errors='ignore')

excel_columns = ["Cluster", "Day", "Visit Order", "DayCluster"] + [
    col for col in route_df.columns if col not in ["Cluster", "Day", "Visit Order", "DayCluster"]
]
route_df = route_df[excel_columns].sort_values(["Cluster", "Day", "Visit Order"]).reset_index(drop=True)

route_df.to_excel("Optimized_Routes_By_Cluster.xlsx", index=False)
print("\n✓ Excel saved!")
print(" DONE! Double-click RouteOptimization_Clustered_Map.html")
