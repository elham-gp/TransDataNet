from pathlib import Path
import osmnx as ox

# ============================================================
# 02_create_segment_network.py
#
# Purpose:
# Load the raw OSM network created by script 01, simplify it
# into a segment-level street network, and save:
#   1. GraphML for later network processing
#   2. GeoPackage for QGIS / GIS inspection
# ============================================================

# -----------------------------
# User settings
# -----------------------------
CITY = "Dresden"

DATA_ROOT = Path(
    r"Z:\_Public\Promotionen\Golpayegani\Paper3\OSM_Network_Simplification\GIS_Data"
)

# -----------------------------
# Input / output folders
# -----------------------------
CITY_DIR = DATA_ROOT / CITY
RAW_DIR = CITY_DIR / "raw"
PROCESSED_DIR = CITY_DIR / "processed"

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# -----------------------------
# Input / output files
# -----------------------------
RAW_GRAPHML = RAW_DIR / f"{CITY.lower()}_raw_osm_network.graphml"

SEGMENT_GRAPHML = PROCESSED_DIR / f"{CITY.lower()}_segment_network.graphml"
SEGMENT_GPKG = PROCESSED_DIR / f"{CITY.lower()}_segment_network.gpkg"

# -----------------------------
# Load raw graph
# -----------------------------
print("=" * 60)
print("Creating segment network")
print(f"City: {CITY}")
print("=" * 60)

if not RAW_GRAPHML.exists():
    raise FileNotFoundError(
        f"Raw GraphML not found:\n{RAW_GRAPHML}\n"
        "Run 01_download_raw_network.py first."
    )

print("Loading raw OSM network...")
G_raw = ox.load_graphml(RAW_GRAPHML)

print("Raw graph:")
print(f"  Nodes: {len(G_raw.nodes):,}")
print(f"  Edges: {len(G_raw.edges):,}")

# -----------------------------
# Simplify graph
# -----------------------------
print("Simplifying graph for segment-level crash analysis...")

G_segment = ox.simplify_graph(G_raw)

print("Segment graph:")
print(f"  Nodes: {len(G_segment.nodes):,}")
print(f"  Edges: {len(G_segment.edges):,}")

# -----------------------------
# Save GraphML
# -----------------------------
print("Saving segment GraphML...")

ox.save_graphml(
    G_segment,
    filepath=SEGMENT_GRAPHML,
)

# -----------------------------
# Convert graph to GIS layers
# -----------------------------
print("Converting graph to GeoDataFrames...")

nodes, edges = ox.graph_to_gdfs(G_segment)

nodes = nodes.reset_index()
edges = edges.reset_index()

# Add stable IDs useful for joins and QGIS
nodes["node_id"] = nodes["osmid"].astype(str)

edges["edge_id"] = (
    edges["u"].astype(str)
    + "_"
    + edges["v"].astype(str)
    + "_"
    + edges["key"].astype(str)
)

edges["segment_id"] = edges.index + 1
edges["analysis_level"] = "segment"

# -----------------------------
# Save GeoPackage
# -----------------------------
print("Saving segment GeoPackage...")

nodes.to_file(
    SEGMENT_GPKG,
    layer="segment_nodes",
    driver="GPKG",
)

edges.to_file(
    SEGMENT_GPKG,
    layer="segment_edges",
    driver="GPKG",
)

print("=" * 60)
print("Done.")
print("Segment GraphML saved to:")
print(f"  {SEGMENT_GRAPHML}")
print("Segment GeoPackage saved to:")
print(f"  {SEGMENT_GPKG}")
print("=" * 60)