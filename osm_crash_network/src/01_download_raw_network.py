from pathlib import Path
import osmnx as ox

# ============================================================
# 01_download_raw_network.py
#
# Purpose:
# Download a raw OSM network for one city and save it outside
# the GitHub repository as:
#   1. GraphML for later network processing
#   2. GeoPackage for QGIS / GIS inspection
# ============================================================

# -----------------------------
# User settings
# -----------------------------
CITY = "Dresden"
COUNTRY = "Germany"

PLACE = f"{CITY}, {COUNTRY}"

NETWORK_TYPE = "all"
# Options:
# "drive" = car network
# "bike"  = cycling network
# "walk"  = pedestrian network
# "all"   = all OSM ways useful for multimodal analysis

# IMPORTANT:
# Change this to your own external GIS data folder.
# Do NOT store large GeoPackage files inside the GitHub repo.
DATA_ROOT = Path(
    r"Z:\_Public\Promotionen\Golpayegani\Paper3\OSM_Network_Simplification\GIS_Data"
)

# -----------------------------
# Output folders
# -----------------------------
CITY_DIR = DATA_ROOT / CITY
RAW_DIR = CITY_DIR / "raw"

RAW_DIR.mkdir(parents=True, exist_ok=True)

# -----------------------------
# Output files
# -----------------------------
RAW_GRAPHML = RAW_DIR / f"{CITY.lower()}_raw_osm_network.graphml"
RAW_GPKG = RAW_DIR / f"{CITY.lower()}_raw_osm_network.gpkg"

# -----------------------------
# Keep useful OSM attributes
# -----------------------------
ox.settings.useful_tags_way = list(
    set(
        ox.settings.useful_tags_way
        + [
            "highway",
            "name",
            "oneway",
            "lanes",
            "maxspeed",
            "sidewalk",
            "sidewalk:left",
            "sidewalk:right",
            "cycleway",
            "cycleway:left",
            "cycleway:right",
            "bicycle",
            "foot",
            "bus",
            "psv",
            "access",
            "surface",
            "lit",
            "railway",
            "tram",
            "service",
            "junction",
            "bridge",
            "tunnel",
        ]
    )
)

# -----------------------------
# Download raw OSM network
# -----------------------------
print("=" * 60)
print("Downloading raw OSM network")
print(f"Place: {PLACE}")
print(f"Network type: {NETWORK_TYPE}")
print("=" * 60)

G_raw = ox.graph_from_place(
    PLACE,
    network_type=NETWORK_TYPE,
    simplify=False,
    retain_all=True,
)

print("Raw graph downloaded:")
print(f"  Nodes: {len(G_raw.nodes):,}")
print(f"  Edges: {len(G_raw.edges):,}")

# -----------------------------
# Project network to metric CRS
# -----------------------------
print("Projecting graph to a metric CRS...")

G_raw_projected = ox.project_graph(G_raw)

print(f"Projected CRS: {G_raw_projected.graph.get('crs')}")

# -----------------------------
# Save GraphML
# -----------------------------
print("Saving raw GraphML...")

ox.save_graphml(
    G_raw_projected,
    filepath=RAW_GRAPHML,
)

# -----------------------------
# Convert graph to GIS layers
# -----------------------------
print("Converting graph to GeoDataFrames...")

nodes, edges = ox.graph_to_gdfs(G_raw_projected)

nodes = nodes.reset_index()
edges = edges.reset_index()

# Add simple IDs useful in QGIS
nodes["node_id"] = nodes["osmid"].astype(str)

edges["edge_id"] = (
    edges["u"].astype(str)
    + "_"
    + edges["v"].astype(str)
    + "_"
    + edges["key"].astype(str)
)

# -----------------------------
# Save GeoPackage
# -----------------------------
print("Saving raw GeoPackage...")

nodes.to_file(
    RAW_GPKG,
    layer="raw_nodes",
    driver="GPKG",
)

edges.to_file(
    RAW_GPKG,
    layer="raw_edges",
    driver="GPKG",
)

print("=" * 60)
print("Done.")
print("Raw GraphML saved to:")
print(f"  {RAW_GRAPHML}")
print("Raw GeoPackage saved to:")
print(f"  {RAW_GPKG}")
print("=" * 60)