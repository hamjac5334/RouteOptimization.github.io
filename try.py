# Filename: RouteMapClustered.py
# Two modes: "Make Route" (click to collect list) and "Close Location" (find 5 nearest)
# Optimize Route calls OpenRouteService directly from the browser — no local server needed.


#Create a panel on the map with 3 check boxes that turn certain circles on and off depending on #what the value is in the "Supplier " column is for each row. Start with all of them checked and #you can deselect the dots if you don't want to include it in the map

# df[["Supplier" = "Island Brands"]]
# df[["Supplier" = "Rusty Bull Brewing Company"]]
# df[["Supplier" = "Southern Barrel Brewing Company"]]



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
    params = {"origins": origins, "destinations": origins,
              "key": GOOGLE_API_KEY, "units": "metric", "mode": "driving"}
    try:
        r = requests.get("https://maps.googleapis.com/maps/api/distancematrix/json",
                         params=params, timeout=15)
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

# ── Input ─────────────────────────────────────────────────────────────────────
num_clusters = int(input("Enter number of clusters (employees): "))

# ── Load ──────────────────────────────────────────────────────────────────────
df = pd.read_csv("CopyofSales_By_Brand_26_124_Month-5_geocodio_b82728e2fe066ceda13ba3e94e27b13649e02571.csv")
df = df.rename(columns={"Geocodio Latitude": "Latitude", "Geocodio Longitude": "Longitude"})
df = df.dropna(subset=["Latitude", "Longitude"]).reset_index(drop=True)
print("Data loaded. Total locations:", len(df))

# ── Clustering ────────────────────────────────────────────────────────────────
transformer = Transformer.from_crs("epsg:4326", "epsg:3857", always_xy=True)
proj = np.array([transformer.transform(lon, lat)
                 for lat, lon in zip(df["Latitude"], df["Longitude"])])
kmeans = KMeans(n_clusters=num_clusters, random_state=42, n_init=20, max_iter=500)
df["Cluster"] = kmeans.fit_predict(proj)
print("\\nCluster counts:")
print(df["Cluster"].value_counts().sort_index())

# ── Routing ───────────────────────────────────────────────────────────────────
print("\\nComputing routes...")
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
excel_cols = ["Cluster", "Visit Order"] + [c for c in route_df.columns
                                            if c not in ["Cluster", "Visit Order"]]
route_df = route_df[excel_cols].sort_values(["Cluster", "Visit Order"]).reset_index(drop=True)
route_df.to_excel("Optimized_Routes_By_Cluster.xlsx", index=False)
print("✓ Excel saved!")

# ── Get unique suppliers for checkboxes ────────────────────────────────────────
unique_suppliers = sorted(df["Supplier"].dropna().unique())
print(f"Found {len(unique_suppliers)} unique suppliers: {unique_suppliers}")

COLORS = ["#0817a1","#f79845","#226b27","#bd32d9","#a30a23",
          "#a335e8","#f011dd","#a30a23","#0817a1","#bd32d9"]

markers_data = []
for idx, row in df.iterrows():
    c = int(row["Cluster"])
    supplier = str(row.get("Supplier", "Unknown"))
    markers_data.append({
        "idx": idx, "lat": float(row["Latitude"]), "lng": float(row["Longitude"]),
        "retailer": str(row["Retailer"]), "address": f"{row['Address']}, {row['City']}",
        "cluster": c + 1, "color": COLORS[c % len(COLORS)],
        "supplier": supplier  # Add supplier info to markers
    })

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

# ── HTML ──────────────────────────────────────────────────────────────────────
html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Route Optimization</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  :root {
    --bg:          #f4f5f7;
    --surface:     #ffffff;
    --surface2:    #f9fafb;
    --border:      #dde1e7;
    --border2:     #c8cdd6;
    --text:        #1c2333;
    --text-mid:    #4a5568;
    --text-dim:    #8896a8;
    --text-faint:  #b8c2cc;
    --accent-l:        #3b5998;
    --accent-l-light:  #edf0f7;
    --accent-l-mid:    #c5cfe8;
    --accent-r:        #217a6b;
    --accent-r-light:  #e8f4f2;
    --accent-r-mid:    #b2d8d2;
    --flash-bg: #fef9c3;
    --flash-bd: #ca8a04;
    --radius:    6px;
    --radius-sm: 4px;
    --shadow:    0 1px 4px rgba(0,0,0,.08), 0 0 1px rgba(0,0,0,.06);
    --shadow-md: 0 2px 8px rgba(0,0,0,.10), 0 0 2px rgba(0,0,0,.05);
  }
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    display: flex; height: 100vh; overflow: hidden;
    font-family: 'Inter', system-ui, sans-serif;
    background: var(--bg); color: var(--text); font-size: 13px;
  }
  .sidebar {
    width: 290px; min-width: 290px; height: 100vh;
    display: flex; flex-direction: column;
    background: var(--surface); overflow: hidden;
    transition: width .3s cubic-bezier(.4,0,.2,1),
                min-width .3s cubic-bezier(.4,0,.2,1),
                opacity .2s ease;
  }
  .sidebar.hidden { width: 0; min-width: 0; opacity: 0; pointer-events: none; }
  #sb-left  { border-right: 1px solid var(--border); box-shadow: var(--shadow); }
  #sb-right { border-left:  1px solid var(--border); box-shadow: var(--shadow); }
  .sb-head { padding: 0; flex-shrink: 0; }
  .sb-title-bar {
    display: flex; align-items: center; gap: 9px;
    padding: 14px 16px 10px; border-bottom: 1px solid var(--border);
  }
  .sb-accent-bar { width: 3px; height: 18px; border-radius: 2px; flex-shrink: 0; }
  #sb-left  .sb-accent-bar { background: var(--accent-l); }
  #sb-right .sb-accent-bar { background: var(--accent-r); }
  .sb-head h2 {
    font-size: 12px; font-weight: 600; letter-spacing: .4px;
    text-transform: uppercase; color: var(--text);
  }
  .sb-head p {
    font-size: 11px; color: var(--text-dim); padding: 7px 16px 9px;
    border-bottom: 1px solid var(--border); background: var(--surface2); line-height: 1.5;
  }
  .sb-count {
    padding: 8px 16px; border-bottom: 1px solid var(--border);
    background: var(--surface2); flex-shrink: 0;
  }
  .badge {
    display: inline-block; font-size: 10.5px; font-weight: 600;
    padding: 2px 9px; border-radius: 20px; letter-spacing: .2px;
  }
  #sb-left  .badge { background: var(--accent-l-light); color: var(--accent-l); border: 1px solid var(--accent-l-mid); }
  #sb-right .badge { background: var(--accent-r-light); color: var(--accent-r); border: 1px solid var(--accent-r-mid); }
  .sb-list {
    flex: 1; overflow-y: auto; padding: 10px;
    display: flex; flex-direction: column; gap: 6px; background: var(--bg);
  }
  .sb-list::-webkit-scrollbar { width: 5px; }
  .sb-list::-webkit-scrollbar-track { background: transparent; }
  .sb-list::-webkit-scrollbar-thumb { background: var(--border2); border-radius: 10px; }
  .empty-msg {
    display: flex; flex-direction: column; align-items: center;
    justify-content: center; padding: 40px 20px; text-align: center;
    color: var(--text-faint); font-size: 12px; line-height: 1.7; gap: 8px; margin-top: 10px;
  }
  .loc-card {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: var(--radius); padding: 10px 12px; position: relative;
    transition: border-color .15s, box-shadow .15s;
    animation: cardIn .15s ease; box-shadow: var(--shadow);
  }
  @keyframes cardIn {
    from { opacity: 0; transform: translateY(4px); }
    to   { opacity: 1; transform: translateY(0); }
  }
  .loc-card:hover { border-color: var(--border2); box-shadow: var(--shadow-md); }
  .loc-card.source-card { border-left: 3px solid var(--accent-l); }
  .loc-card.flash { background: var(--flash-bg) !important; border-color: var(--flash-bd) !important; }
  .loc-card.optimized { border-left: 3px solid var(--accent-r); }
  .order-num {
    position: absolute; top: 10px; right: 12px;
    min-width: 20px; height: 20px; border-radius: 4px;
    background: var(--accent-r-light); color: var(--accent-r);
    border: 1px solid var(--accent-r-mid);
    font-size: 10px; font-weight: 600;
    display: flex; align-items: center; justify-content: center; padding: 0 4px;
  }
  .del-btn {
    position: absolute; top: 8px; right: 10px;
    width: 22px; height: 22px; border-radius: var(--radius-sm);
    background: transparent; border: 1px solid transparent;
    color: var(--text-faint); font-size: 15px; cursor: pointer; line-height: 1;
    display: flex; align-items: center; justify-content: center;
    transition: background .12s, border-color .12s, color .12s;
  }
  .del-btn:hover { background: #fef2f2; border-color: #fca5a5; color: #dc2626; }
  .card-name {
    font-weight: 600; font-size: 12.5px; color: var(--text);
    padding-right: 34px; margin-bottom: 5px; line-height: 1.4;
  }
  .card-tags { display: flex; gap: 4px; margin-bottom: 5px; flex-wrap: wrap; }
  .tag { font-size: 10px; font-weight: 500; padding: 1px 7px; border-radius: 20px; border: 1px solid transparent; }
  .tag-emp  { background: var(--accent-l-light); color: var(--accent-l); border-color: var(--accent-l-mid); }
  .tag-dist { background: #f0fdf4; color: #15803d; border-color: #bbf7d0; }
  .tag-src  { background: var(--accent-l-light); color: var(--accent-l); border-color: var(--accent-l-mid); font-style: italic; }
  .tag-opt  { background: #fdf4ff; color: #7e22ce; border-color: #e9d5ff; }
  .card-addr { font-size: 11px; color: var(--text-dim); line-height: 1.45; }
  .sb-foot {
    padding: 10px; border-top: 1px solid var(--border);
    background: var(--surface); flex-shrink: 0;
    display: flex; flex-direction: column; gap: 6px;
  }
  .clr-btn {
    width: 100%; padding: 8px 12px; border-radius: var(--radius);
    border: 1px solid var(--border2); background: var(--surface2);
    color: var(--text-mid); font-family: inherit; font-size: 11.5px;
    font-weight: 500; cursor: pointer;
    transition: background .12s, border-color .12s, color .12s;
    display: flex; align-items: center; justify-content: center; gap: 6px;
  }
  .clr-btn:hover { background: #fef2f2; border-color: #fca5a5; color: #dc2626; }

  /* Optimize button */
  #btn-optimize {
    width: 100%; padding: 9px 12px; border-radius: var(--radius);
    border: 1px solid var(--accent-r-mid); background: var(--accent-r-light);
    color: var(--accent-r); font-family: inherit; font-size: 12px; font-weight: 600;
    cursor: pointer; transition: background .15s, border-color .15s, color .15s;
    display: flex; align-items: center; justify-content: center; gap: 7px;
  }
  #btn-optimize:hover:not(:disabled) { background: #c5e8e3; border-color: #217a6b; color: #155f52; }
  #btn-optimize:disabled { opacity: .45; cursor: not-allowed; }
  .spin {
    width: 13px; height: 13px;
    border: 2px solid var(--accent-r-mid); border-top-color: var(--accent-r);
    border-radius: 50%; animation: spin .6s linear infinite; flex-shrink: 0;
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  /* Toast */
  #toast {
    position: fixed; bottom: 80px; left: 50%; transform: translateX(-50%);
    background: var(--text); color: #fff; padding: 8px 18px; border-radius: 20px;
    font-size: 12px; font-weight: 500; opacity: 0; pointer-events: none;
    transition: opacity .25s ease; z-index: 9999; white-space: nowrap;
    box-shadow: 0 4px 12px rgba(0,0,0,.25);
  }
  #toast.show    { opacity: 1; }
  #toast.error   { background: #dc2626; }
  #toast.success { background: #16a34a; }

  #map-wrap { flex: 1; position: relative; min-width: 0; }
  #map { width: 100%; height: 100%; }
  
  /* SUPPLIER FILTER PANEL */
  #supplier-panel {
    position: absolute; right: 500px; z-index: 1000;
    background: var(--surface); border: 1px solid var(--border);
    border-radius: var(--radius); padding: 12px; box-shadow: var(--shadow-md);
    min-width: 220px; max-height: 300px; overflow-y: auto;
  }
  #supplier-panel::-webkit-scrollbar { width: 6px; }
  #supplier-panel::-webkit-scrollbar-track { background: var(--surface2); border-radius: 3px; }
  #supplier-panel::-webkit-scrollbar-thumb { background: var(--border2); border-radius: 3px; }
  .panel-title {
    font-size: 12px; font-weight: 600; margin-bottom: 10px; padding-bottom: 8px;
    border-bottom: 1px solid var(--border); color: var(--text);
  }
  .supplier-checkbox {
    display: flex; align-items: center; gap: 8px; margin-bottom: 8px;
    cursor: pointer; padding: 4px 0; font-size: 12px;
  }
  .supplier-checkbox input[type="checkbox"] {
    width: 16px; height: 16px; accent-color: var(--accent-l); cursor: pointer;
  }
  .supplier-checkbox:hover { background: var(--surface2); border-radius: var(--radius-sm); padding: 4px 6px; }
  .supplier-label { line-height: 1.3; color: var(--text); user-select: none; }
  
  #mode-bar {
    position: absolute; bottom: 28px; left: 50%; transform: translateX(-50%);
    display: flex; z-index: 1000;
    background: var(--surface); border: 1px solid var(--border2);
    border-radius: 8px; padding: 4px; gap: 4px; box-shadow: var(--shadow-md);
  }
  .mode-btn {
    padding: 9px 22px; font-family: inherit; font-size: 12px; font-weight: 500;
    cursor: pointer; border: 1px solid transparent; border-radius: 5px;
    background: transparent; color: var(--text-mid);
    transition: background .15s, border-color .15s, color .15s;
    display: flex; align-items: center; gap: 6px; white-space: nowrap;
  }
  .mode-btn:hover { background: var(--surface2); color: var(--text); }
  #btn-close.active { background: var(--accent-l-light); border-color: var(--accent-l-mid); color: var(--accent-l); font-weight: 600; }
  #btn-route.active { background: var(--accent-r-light); border-color: var(--accent-r-mid); color: var(--accent-r); font-weight: 600; }
  .mode-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
  #btn-close .mode-dot { background: var(--accent-l); }
  #btn-route .mode-dot { background: var(--accent-r); }
  .leaflet-tooltip {
    background: var(--surface) !important; border: 1px solid var(--border2) !important;
    border-radius: var(--radius) !important; box-shadow: var(--shadow-md) !important;
    color: var(--text) !important; font-family: 'Inter', system-ui, sans-serif !important;
    font-size: 12px !important; padding: 6px 10px !important;
  }
  .leaflet-tooltip::before { display: none !important; }
</style>
</head>
<body>

<!-- SUPPLIER FILTER PANEL -->
<div id="supplier-panel">
  <div class="panel-title">Filter by Supplier</div>
  <div id="supplier-checkboxes"></div>
</div>

<!-- LEFT: Close Location -->
<div id="sb-left" class="sidebar">
  <div class="sb-head">
    <div class="sb-title-bar"><div class="sb-accent-bar"></div><h2>Close Locations</h2></div>
    <p>5 nearest locations to your selected marker</p>
  </div>
  <div class="sb-count"><span id="close-badge" class="badge">0 shown</span></div>
  <div id="close-list" class="sb-list">
    <div class="empty-msg"><span>Click any marker on the map<br>to find its 5 nearest neighbors.</span></div>
  </div>
  <div class="sb-foot">
    <button class="clr-btn" id="btn-clear-close">&#10005;&nbsp; Clear Results</button>
  </div>
</div>

<!-- MAP -->
<div id="map-wrap">
  <div id="map"></div>
  <div id="mode-bar">
    <button id="btn-close" class="mode-btn active"><span class="mode-dot"></span> Close Location</button>
    <button id="btn-route" class="mode-btn"><span class="mode-dot"></span> Make Route</button>
  </div>
</div>

<!-- RIGHT: Route List -->
<div id="sb-right" class="sidebar hidden">
  <div class="sb-head">
    <div class="sb-title-bar"><div class="sb-accent-bar"></div><h2>Route List</h2></div>
    <p>Click markers to add stops, then hit Optimize Route for the best driving order.</p>
  </div>
  <div class="sb-count"><span id="route-badge" class="badge">0 selected</span></div>
  <div id="route-list" class="sb-list">
    <div class="empty-msg"><span>No stops added yet.<br>Click markers on the map<br>to build your route.</span></div>
  </div>
  <div class="sb-foot">
    <button id="btn-optimize" disabled>
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>
      </svg>
      Optimize Route
    </button>
    <button class="clr-btn" id="btn-clear-route">&#10005;&nbsp; Clear All</button>
  </div>
</div>

<div id="toast"></div>

<script>
var MARKERS = """ + markers_json + """;
var BOXES   = """ + boxes_json   + """;
var SUPPLIERS = """ + suppliers_json + """;
var CENTER  = [""" + str(center_lat) + "," + str(center_lng) + """];
var ORS_API_KEY = "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6ImY2OTY4YjgxYTUxMjQwYmNiNjAxNzk4ZTY4YzEyNzlhIiwiaCI6Im11cm11cjY0In0=";

// ── Map ────────────────────────────────────────────────────────────────────
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

// ── SUPPLIER FILTER ─────────────────────────────────────────────────────────
var layerMap = {}, supplierVisibility = {};
var allMarkersVisible = true;

// Initialize supplier checkboxes (all checked by default)
function initSupplierFilter() {
  SUPPLIERS.forEach(function(supplier) {
    supplierVisibility[supplier] = true;
  });
  
  var checkboxesContainer = document.getElementById('supplier-checkboxes');
  SUPPLIERS.forEach(function(supplier, index) {
    var checkboxDiv = document.createElement('div');
    checkboxDiv.className = 'supplier-checkbox';
    checkboxDiv.innerHTML = `
      <input type="checkbox" id="chk-${index}" checked onchange="toggleSupplier('${supplier}')">
      <label for="chk-${index}" class="supplier-label">${supplier}</label>
    `;
    checkboxesContainer.appendChild(checkboxDiv);
  });
}

// Toggle supplier visibility
function toggleSupplier(supplier) {
  supplierVisibility[supplier] = !supplierVisibility[supplier];
  updateMarkerVisibility();
}

function updateMarkerVisibility() {
  MARKERS.forEach(function(m) {
    var circle = layerMap[m.idx];
    if (circle) {
      var shouldShow = supplierVisibility[m.supplier] || !allMarkersVisible;
      if (shouldShow) {
        circle.setStyle({radius:7, color:'#ffffff', weight:1.5, fillColor:m.color, fillOpacity:0.85});
        circle.addTo(map);
      } else {
        map.removeLayer(circle);
      }
    }
  });
}

// ── State ──────────────────────────────────────────────────────────────────
var mode='close', highlightedIdx=[],
    routeSel={}, routeOrder=[], isOptimizing=false;

// ── Markers ────────────────────────────────────────────────────────────────
MARKERS.forEach(function(m) {
  var circle = L.circleMarker([m.lat, m.lng], {
    radius:7, color:'#ffffff', weight:1.5, fillColor:m.color, fillOpacity:0.85
  });
  circle.bindTooltip(
    '<b>'+esc(m.retailer)+'</b><br>'+
    '<span style="color:#6b7280">Employee '+m.cluster+' | '+esc(m.supplier)+'&nbsp;&middot;&nbsp;'+esc(m.address)+'</span>',
    {direction:'top', offset:[0,-9], sticky:false}
  );
  circle.on('click', function(){ onMarkerClick(m); });
  layerMap[m.idx] = circle;
});

initSupplierFilter();
updateMarkerVisibility();

// ── Mode switching ─────────────────────────────────────────────────────────
document.getElementById('btn-close').addEventListener('click', function(){ setMode('close'); });
document.getElementById('btn-route').addEventListener('click', function(){ setMode('route'); });

function setMode(m) {
  mode=m;
  document.getElementById('btn-close').classList.toggle('active', m==='close');
  document.getElementById('btn-route').classList.toggle('active', m==='route');
  document.getElementById('sb-left').classList.toggle('hidden',  m!=='close');
  document.getElementById('sb-right').classList.toggle('hidden', m!=='route');
  if(m!=='close') clearHighlights();
}

// ── Haversine ──────────────────────────────────────────────────────────────
function hvs(lat1,lng1,lat2,lng2) {
  var R=6371, dLat=(lat2-lat1)*Math.PI/180, dLng=(lng2-lng1)*Math.PI/180;
  var a=Math.sin(dLat/2)*Math.sin(dLat/2)+
        Math.cos(lat1*Math.PI/180)*Math.cos(lat2*Math.PI/180)*
        Math.sin(dLng/2)*Math.sin(dLng/2);
  return R*2*Math.atan2(Math.sqrt(a),Math.sqrt(1-a));
}

function clearHighlights() {
  highlightedIdx.forEach(function(idx){
    var m=MARKERS.find(function(x){return x.idx===idx;});
    if(m&&layerMap[idx])
      layerMap[idx].setStyle({radius:7,color:'#ffffff',weight:1.5,fillColor:m.color,fillOpacity:0.85});
  });
  highlightedIdx=[];
}

function onMarkerClick(m){ if(mode==='close') doClose(m); else doRoute(m); }

// ── CLOSE LOCATION ─────────────────────────────────────────────────────────
function doClose(src) {
  clearHighlights();
  var dists=MARKERS
    .filter(function(m){return m.idx!==src.idx;})
    .map(function(m){return{m:m,d:hvs(src.lat,src.lng,m.lat,m.lng)};})
    .sort(function(a,b){return a.d-b.d;});
  var top5=dists.slice(0,5);
  layerMap[src.idx].setStyle({radius:11,color:'#1d4ed8',weight:2.5,fillColor:'#3b82f6',fillOpacity:1});
  highlightedIdx.push(src.idx);
  top5.forEach(function(e){
    layerMap[e.m.idx].setStyle({radius:9,color:'#000000',weight:2,fillColor:'#ffee30',fillOpacity:1});
    highlightedIdx.push(e.m.idx);
  });
  var list=document.getElementById('close-list');
  list.innerHTML='';
  list.appendChild(buildCloseCard(src,null,true));
  top5.forEach(function(e){
    var ds=e.d<1?(e.d*1000).toFixed(0)+' m':e.d.toFixed(2)+' km';
    list.appendChild(buildCloseCard(e.m,ds,false));
  });
  document.getElementById('close-badge').textContent='5 shown';
}

function buildCloseCard(m,distStr,isSource) {
  var card=document.createElement('div');
  card.className='loc-card'+(isSource?' source-card':'');
  var tags='<span class="tag tag-emp">Employee '+m.cluster+'</span>';
  if(distStr)  tags+='<span class="tag tag-dist">'+distStr+' away</span>';
  if(isSource) tags+='<span class="tag tag-src">Selected</span>';
  card.innerHTML='<div class="card-name">'+esc(m.retailer)+'</div>'+
    '<div class="card-tags">'+tags+'</div>'+
    '<div class="card-addr">'+esc(m.address)+'</div>';
  return card;
}

document.getElementById('btn-clear-close').addEventListener('click', function(){
  clearHighlights();
  document.getElementById('close-list').innerHTML=
    '<div class="empty-msg"><span>Click any marker on the map<br>to find its 5 nearest neighbors.</span></div>';
  document.getElementById('close-badge').textContent='0 shown';
});

// ── MAKE ROUTE ─────────────────────────────────────────────────────────────
function doRoute(m) {
  if(isOptimizing) return;
  var key=String(m.idx);
  if(routeSel[key]){
    var el=document.getElementById('rc-'+key);
    if(el){el.classList.add('flash');setTimeout(function(){el.classList.remove('flash');},700);}
    return;
  }
  routeSel[key]=m; routeOrder.push(key);
  var emp=document.getElementById('route-list').querySelector('.empty-msg');
  if(emp) emp.remove();
  document.getElementById('route-list').appendChild(buildRouteCard(m,routeOrder.length,key));
  updateRouteBadge(); updateOptimizeBtn();
}

function buildRouteCard(m,num,key) {
  var card=document.createElement('div');
  card.className='loc-card'; card.id='rc-'+key;
  var orderNum=document.createElement('div');
  orderNum.className='order-num'; orderNum.textContent=num;
  var delBtn=document.createElement('button');
  delBtn.className='del-btn'; delBtn.title='Remove stop'; delBtn.innerHTML='&times;';
  delBtn.addEventListener('click',function(e){e.stopPropagation();removeRoute(key);});
  var nameEl=document.createElement('div');
  nameEl.className='card-name'; nameEl.textContent=m.retailer; nameEl.style.paddingRight='36px';
  var tagsEl=document.createElement('div');
  tagsEl.className='card-tags';
  tagsEl.innerHTML='<span class="tag tag-emp">Employee '+m.cluster+'</span><span class="tag tag-emp">'+esc(m.supplier)+'</span>';
  var addrEl=document.createElement('div');
  addrEl.className='card-addr'; addrEl.textContent=m.address;
  card.appendChild(orderNum); card.appendChild(delBtn);
  card.appendChild(nameEl); card.appendChild(tagsEl); card.appendChild(addrEl);
  return card;
}

function removeRoute(key) {
  if(isOptimizing||!routeSel[key]) return;
  delete routeSel[key];
  routeOrder=routeOrder.filter(function(k){return k!==key;});
  var el=document.getElementById('rc-'+key);
  if(el){
    el.style.transition='opacity .12s ease, transform .12s ease';
    el.style.opacity='0'; el.style.transform='translateX(10px)';
    setTimeout(function(){
      if(el.parentNode) el.parentNode.removeChild(el);
      renumberCards();
    },130);
  }
  if(routeOrder.length===0){
    setTimeout(function(){
      if(routeOrder.length===0)
        document.getElementById('route-list').innerHTML=
          '<div class="empty-msg"><span>No stops added yet.<br>Click markers on the map<br>to build your route.</span></div>';
    },150);
  }
  updateRouteBadge(); updateOptimizeBtn();
}

function renumberCards(){
  routeOrder.forEach(function(key,i){
    var el=document.getElementById('rc-'+key);
    if(el){var n=el.querySelector('.order-num');if(n)n.textContent=i+1;}
  });
}

document.getElementById('btn-clear-route').addEventListener('click', function(){
  if(isOptimizing) return;
  routeSel={}; routeOrder=[];
  document.getElementById('route-list').innerHTML=
    '<div class="empty-msg"><span>No stops added yet.<br>Click markers on the map<br>to build your route.</span></div>';
  updateRouteBadge(); updateOptimizeBtn();
});

function updateRouteBadge(){ document.getElementById('route-badge').textContent=routeOrder.length+' selected'; }
function updateOptimizeBtn(){ document.getElementById('btn-optimize').disabled=routeOrder.length<2||isOptimizing; }

// ── OPTIMIZE ROUTE via OpenRouteService (first stop fixed) ─────────────────
document.getElementById('btn-optimize').addEventListener('click', optimizeRoute);

function optimizeRoute() {
  if(isOptimizing||routeOrder.length<2) return;

  isOptimizing=true;
  var btn = document.getElementById('btn-optimize');
  btn.disabled=true;
  btn.innerHTML='<div class="spin"></div> Optimizing…';

  var stops = routeOrder.map(function(key){ return routeSel[key]; });

  // keep first selected stop as fixed start/end
  var firstStop = stops[0];
  var firstKey  = routeOrder[0];

  // jobs = all stops except the first
  var jobs = stops.slice(1).map(function(s, i) {
    return { id: i, location: [s.lng, s.lat] };
  });

  var payload = {
    jobs: jobs,
    vehicles: [{
      id: 0,
      profile: "driving-car",
      start: [firstStop.lng, firstStop.lat],
      end:   [firstStop.lng, firstStop.lat]
    }]
  };

  fetch("https://api.openrouteservice.org/optimization", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": ORS_API_KEY
    },
    body: JSON.stringify(payload)
  })
  .then(function(res) {
    return res.json().then(function(data) {
      if(!res.ok) {
        var msg = (data.error && data.error.message) || JSON.stringify(data);
        throw new Error(msg);
      }
      return data;
    });
  })
  .then(function(data) {
    var steps = data.routes && data.routes[0] && data.routes[0].steps;
    if(!steps) throw new Error("No route returned from ORS");

    var orderedIndices = steps
      .filter(function(s){ return s.type === "job"; })
      .map(function(s){ return s.id; });

    if(orderedIndices.length !== stops.length - 1) {
      throw new Error("ORS returned " + orderedIndices.length +
                      " steps for " + (stops.length - 1) + " jobs");
    }

    applyOptimizedOrder(firstKey, orderedIndices);
    showToast("Route optimized! 🚗", "success");
  })
  .catch(function(err) {
    console.error("ORS optimize error:", err);
    var msg = String(err.message||err);
    if(msg.toLowerCase().includes("fetch") || msg.toLowerCase().includes("failed to fetch")) {
      showToast("Network error — check your internet connection.", "error");
    } else if(msg.toLowerCase().includes("403") || msg.toLowerCase().includes("401")) {
      showToast("Invalid ORS API key — check ORS_API_KEY in the HTML.", "error");
    } else if(msg.toLowerCase().includes("429")) {
      showToast("ORS rate limit hit — wait a moment and try again.", "error");
    } else {
      showToast("Optimization error: " + msg, "error");
    }
    resetOptimizeBtn();
  });
}

function applyOptimizedOrder(firstKey, order) {
  // all current stops (in their pre-optimization order)
  var allStops = routeOrder.map(function(key){ return routeSel[key]; });
  // jobs correspond to all stops except the first
  var otherStops = allStops.slice(1);

  // map ORS job ids back to our keys
  var orderedKeys = order.map(function(i) {
    return String(otherStops[i].idx);
  });

  // prepend the original first stop so it always stays #1 in UI
  routeOrder = [String(firstKey)].concat(orderedKeys);

  var list=document.getElementById('route-list');
  var cards=list.querySelectorAll('.loc-card');
  cards.forEach(function(c){
    c.style.transition='opacity .15s ease';
    c.style.opacity='0';
  });

  setTimeout(function(){
    list.innerHTML='';
    routeOrder.forEach(function(key,i){
      var m=routeSel[key];
      var card=buildRouteCard(m,i+1,key);
      card.classList.add('optimized');
      var tagsEl=card.querySelector('.card-tags');
      var optTag=document.createElement('span');
      optTag.className='tag tag-opt';
      optTag.textContent=(i===0 ? '✦ Start (fixed)' : '✦ Optimized');
      tagsEl.appendChild(optTag);
      list.appendChild(card);
    });
    resetOptimizeBtn();
  },200);
}

function resetOptimizeBtn(){
  isOptimizing=false;
  var btn=document.getElementById('btn-optimize');
  btn.innerHTML='<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg> Optimize Route';
  btn.disabled=routeOrder.length<2;
}

function showToast(msg,type){
  var t=document.getElementById('toast');
  t.textContent=msg; t.className='show '+(type||'');
  clearTimeout(t._timer);
  t._timer=setTimeout(function(){t.className='';},3800);
}
function esc(s){
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

setMode('close');
</script>
</body>
</html>"""

with open("RouteOptimization_Clustered_Map.html", "w", encoding="utf-8") as f:
    f.write(html)

print("✓ HTML map with supplier filter panel saved to RouteOptimization_Clustered_Map.html!")
