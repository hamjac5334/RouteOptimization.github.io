# Filename: RouteMapClustered.py
# Two modes: "Make Route" (click to collect list) and "Close Location" (find 5 nearest)
# Optimize Route calls OpenRouteService directly from the browser — no local server needed.
#Create a panel on the map with 3 check boxes that turn certain circles on and off depending on #what the value is in the "Supplier " column is for each row. Start with all of them checked and #you can deselect the dots if you don't want to include it in the map

# df[["Supplier" = "Island Brands"]]
# df[["Supplier" = "Rusty Bull Brewing Company"]]
# df[["Supplier" = "Southern Barrel Brewing Company"]]


import sys
import pandas as pd
import numpy as np
import requests
import time
import json
from sklearn.cluster import KMeans
from pyproj import Transformer
import warnings
warnings.filterwarnings("ignore")

GOOGLE_API_KEY = "AIzaSyDSd-fc2wicMn2lT5L6MA5ikQrq6EPV0PQ"

def get_driving_distance_matrix(coords):
    n = len(coords)
    if n > 25:
        mid = n // 2
        d1 = get_driving_distance_matrix(coords[:mid])
        d2 = get_driving_distance_matrix(coords[mid:])
        if d1 is None or d2 is None:
            return None
        full = np.full((n, n), np.inf)
        n1 = len(d1)
        full[:n1, :n1] = d1
        full[n1:, n1:] = d2
        return full
    origins = "|".join([f"{lat},{lon}" for lat, lon in coords])
    params = {
        "origins": origins,
        "destinations": origins,
        "key": GOOGLE_API_KEY,
        "units": "metric",
        "mode": "driving",
    }
    try:
        r = requests.get(
            "https://maps.googleapis.com/maps/api/distancematrix/json",
            params=params,
            timeout=15,
        )
        data = r.json()
    except Exception as e:
        print(f"  API request failed: {e}")
        return None
    if data.get("status") != "OK":
        print(f"  API error: {data.get('status')} — {data.get('error_message','')}")
        return None
    dm = np.full((n, n), np.inf)
    for i in range(n):
        for j in range(n):
            try:
                el = data["rows"][i]["elements"][j]
                if el["status"] == "OK":
                    dm[i, j] = el["distance"]["value"]
            except (IndexError, KeyError):
                pass
    time.sleep(0.1)
    return dm

def straight_line_matrix(coords):
    from math import radians, cos, sin, sqrt, atan2
    n = len(coords)
    dm = np.zeros((n, n))
    R = 6_371_000
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            lat1, lon1 = map(radians, coords[i])
            lat2, lon2 = map(radians, coords[j])
            dlat, dlon = lat2 - lat1, lon2 - lon1
            a = sin(dlat/2)**2 + cos(lat1)*cos(lat2)*sin(dlon/2)**2
            dm[i, j] = R * 2 * atan2(sqrt(a), sqrt(1 - a))
    return dm

def compute_route_order(coords):
    n = len(coords)
    if n <= 1:
        return list(range(n))
    print(f"  Computing driving matrix for {n} points...")
    dm = get_driving_distance_matrix(coords)
    if dm is None:
        print("  Falling back to straight-line distances.")
        dm = straight_line_matrix(coords)
    np.fill_diagonal(dm, 0)
    visited = [0]
    while len(visited) < n:
        last = visited[-1]
        row = dm[last].copy()
        for v in visited:
            row[v] = np.inf
        visited.append(int(np.argmin(row)))
    return visited

# ----------------- VISITS LOADING -----------------

if len(sys.argv) > 1:
    visits_file = sys.argv[1]
else:
    visits_file = "visitsreport2026-03-09-2.csv"

print(f"Using CSV: {visits_file}")
visits = pd.read_csv(visits_file)

print("\n=== RAW 'Visit Date' SAMPLE ===")
print(visits["Visit Date"].head().tolist())

# Parse dates (if needed, adapt pattern to match your file exactly)
visits["Visit Date"] = pd.to_datetime(
    visits["Visit Date"],
    errors="coerce",
)

print("\n=== PARSED 'Visit Date' SAMPLE ===")
print(visits["Visit Date"].head().tolist())
print("NaT count:", visits["Visit Date"].isna().sum(), "/", len(visits))

visits["Business Name"] = visits["Business Name"].astype(str).str.strip()

# Normalize business names (same logic as your working script)
def normalize_name(s):
    if pd.isna(s):
        return ""
    s = str(s).strip().lower()
    for suffix in [" inc.", " inc", " llc", ",", "."]:
        s = s.replace(suffix, "")
    return " ".join(s.split())

visits["Business Name Norm"] = visits["Business Name"].apply(normalize_name)

visits_latest = (
    visits.dropna(subset=["Visit Date"])
    .sort_values("Visit Date")
    .groupby("Business Name Norm", as_index=False)
    .last()
)

visit_map = dict(zip(visits_latest["Business Name Norm"], visits_latest["Visit Date"]))
today = pd.Timestamp.today().normalize()
print(f"Unique businesses with valid dates: {len(visit_map)}")

# Quick debug distribution (optional)
days_ago = (today - visits_latest["Visit Date"].dt.normalize()).dt.days
print("\n=== COLOR DISTRIBUTION (debug) ===")
print(
    pd.cut(
        days_ago,
        bins=[-1, 7, 14, 21, 10_000],
        labels=["green (<=7d)", "orange (<=14d)", "red (<=21d)", "dark red (>21d)"],
    ).value_counts()
)

def get_visit_color(retailer):
    key = normalize_name(retailer)
    visit_date = visit_map.get(key)

    if visit_date is None or pd.isna(visit_date):
        return "#7f1d1d"  # dark red if no visit

    days = (today - visit_date.normalize()).days

    if days <= 7:
        return "#16a34a"
    elif days <= 14:
        return "#f97316"
    elif days <= 21:
        return "#fc1414"
    else:
        return "#7f1d1d"

# ----------------- CLUSTER, ROUTES, MARKERS -----------------

num_clusters = 5

df = pd.read_csv("Corrected_OnPremise_geocodio_6374dbcbfa65642924f84331d8d4bf80865cf20b.csv")
df = df.rename(columns={"Geocodio Latitude": "Latitude", "Geocodio Longitude": "Longitude"})
df = df.dropna(subset=["Latitude", "Longitude"]).reset_index(drop=True)
print("Data loaded. Total locations:", len(df))

transformer = Transformer.from_crs("epsg:4326", "epsg:3857", always_xy=True)
proj = np.array([transformer.transform(lon, lat)
                 for lat, lon in zip(df["Latitude"], df["Longitude"])])
kmeans = KMeans(n_clusters=num_clusters, random_state=42, n_init=20, max_iter=500)
df["Cluster"] = kmeans.fit_predict(proj)
print("\nCluster counts:")
print(df["Cluster"].value_counts().sort_index())

print("\nComputing routes...")
route_output = []
for cluster_id, group in df.groupby("Cluster"):
    print(f"  Cluster {cluster_id + 1} ({len(group)} pts)")
    cdf = group.copy()
    coords = cdf[["Latitude", "Longitude"]].values.tolist()
    order = compute_route_order(coords)
    cdf = cdf.iloc[order].reset_index(drop=True)
    cdf["Visit Order"] = range(1, len(cdf) + 1)
    cdf["Cluster"] = cluster_id + 1
    route_output.append(cdf)

route_df = pd.concat(route_output, ignore_index=True)
geocode_cols = [c for c in route_df.columns if c.startswith("Geocodio")]
route_df = route_df.drop(columns=geocode_cols + ["Latitude", "Longitude"], errors="ignore")
excel_cols = ["Cluster", "Visit Order"] + [
    c for c in route_df.columns if c not in ["Cluster", "Visit Order"]
]
route_df = route_df[excel_cols].sort_values(["Cluster", "Visit Order"]).reset_index(drop=True)
route_df.to_excel("Optimized_Routes_By_Cluster.xlsx", index=False)
print("✓ Excel saved!")

unique_suppliers = sorted(df["Supplier"].dropna().unique())
print(f"Found {len(unique_suppliers)} unique suppliers: {unique_suppliers}")

COLORS = ["#0817a1","#f79845","#226b27","#bd32d9","#a30a23",
          "#a335e8","#f011dd","#a30a23","#0817a1","#bd32d9"]

grouped = (
    df.groupby(
        ["Retailer", "Address", "City", "Latitude", "Longitude", "Cluster"]
    )
    .agg({
        "Supplier": lambda x: sorted(set(x.dropna()))
    })
    .reset_index()
)

markers_data = []
for idx, row in grouped.iterrows():
    c = int(row["Cluster"])
    suppliers = row["Supplier"]

    visit_color = get_visit_color(row["Retailer"])

    markers_data.append({
        "idx": idx,
        "lat": float(row["Latitude"]),
        "lng": float(row["Longitude"]),
        "retailer": str(row["Retailer"]),
        "address": f"{row['Address']}, {row['City']}",
        "cluster": c + 1,
        "color": COLORS[c % len(COLORS)],
        "visit_color": visit_color,
        "suppliers": suppliers
    })

# Optional debugging
colors_assigned = {}
for m in markers_data:
    colors_assigned[m["visit_color"]] = colors_assigned.get(m["visit_color"], 0) + 1
print("\n=== VISIT COLOR DISTRIBUTION IN MARKERS ===")
print(colors_assigned)

print("\n=== SAMPLE RETAILER LOOKUPS ===")
for m in markers_data[:10]:
    retailer = m["retailer"]
    key = normalize_name(retailer)
    visit_date = visit_map.get(key)
    print(f"  '{retailer}' → {visit_date} → {m['visit_color']}")

boxes = []
for cluster_id in sorted(df["Cluster"].unique()):
    sub = df[df["Cluster"] == cluster_id]
    boxes.append({"color": COLORS[cluster_id % len(COLORS)], "bounds": [
        [float(sub["Latitude"].min()), float(sub["Longitude"].min())],
        [float(sub["Latitude"].max()), float(sub["Longitude"].max())],
    ]})

center_lat = float(df["Latitude"].mean())
center_lng = float(df["Longitude"].mean())
markers_json = json.dumps(markers_data)
boxes_json   = json.dumps(boxes)
suppliers_json = json.dumps(unique_suppliers)

# HTML (only small JS tweaks vs your version)
html = """<!DOCTYPE html>
<html lang="en">
<head>
...
</head>
<body>
...
<script>
var MARKERS = """ + markers_json + """;
var BOXES   = """ + boxes_json   + """;
var SUPPLIERS = """ + suppliers_json + """;
var CENTER  = [""" + str(center_lat) + "," + str(center_lng) + """];
var ORS_API_KEY = "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6ImY2OTY4YjgxYTUxMjQwYmNiNjAxNzk4ZTY4YzEyNzlhIiwiaCI6Im11cm11cjY0In0=";

var map = L.map('map', {zoomControl:true}).setView(CENTER, 12);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  attribution: '&copy; <a href="https://openstreetmap.org">OpenStreetMap</a>', maxZoom:19
}).addTo(map);

BOXES.forEach(function(b) {
  L.rectangle(b.bounds, {
    color:b.color, weight:1.5, opacity:0.35,
    fill:true, fillColor:b.color, fillOpacity:0.04, dashArray:'4 4'
  }).addTo(map);
});

var layerMap = {}, supplierVisibility = {};
var mode='close', highlightedIdx=[],
    routeSel={}, routeOrder=[], isOptimizing=false,
    visitMode=false;

// Supplier filter init unchanged...

function updateMarkerVisibility() {
  MARKERS.forEach(function(m) {
    var circle = layerMap[m.idx];
    if (circle) {
      var shouldShow = Array.isArray(m.suppliers)
        ? m.suppliers.some(function(s){ return supplierVisibility[s]; })
        : supplierVisibility[m.suppliers];

      if (shouldShow) {
        circle.setStyle({
          radius:7, color:'#ffffff', weight:1.5,
          fillColor: visitMode ? m.visit_color : m.color,
          fillOpacity:0.85
        });
        circle.addTo(map);
      } else {
        map.removeLayer(circle);
      }
    }
  });
}

// Markers creation same as before (use m.color initially)...

document.getElementById('btn-visits').addEventListener('click', function(){
  visitMode = !visitMode;
  if (visitMode) {
    this.style.background = "#111827";
    this.style.color = "white";
  } else {
    this.style.background = "white";
    this.style.color = "#374151";
  }
  updateMarkerVisibility();
});

function clearHighlights() {
  highlightedIdx.forEach(function(idx){
    var m=MARKERS.find(function(x){return x.idx===idx;});
    if(m&&layerMap[idx])
      layerMap[idx].setStyle({
        radius:7,color:'#ffffff',weight:1.5,
        fillColor: visitMode ? m.visit_color : m.color,
        fillOpacity:0.85
      });
  });
  highlightedIdx=[];
}

// ...rest of your JS unchanged...
setMode('close');
</script>
</body>
</html>"""

with open("RouteOptimization_OnPremise_Map.html", "w", encoding="utf-8") as f:
    f.write(html)

print("✓ HTML map with supplier filter panel saved to RouteOptimization_OnPremise_Map.html!")

