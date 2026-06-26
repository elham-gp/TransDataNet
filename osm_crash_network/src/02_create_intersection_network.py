from pathlib import Path

import geopandas as gpd
import osmnx as ox

# ============================================================
# 03_create_intersection_network.py
#
# Purpose:
# Create stricter junction areas for crash analysis.
#
# Instead of using all nodes with street_count >= 3, this script:
# 1. Loads the segment network
# 2. Counts only relevant road connections at each node
# 3. Keeps nodes connected to at least 3 relevant road edges
# 4. Buffers these nodes
# 5. Dissolves overlapping buffers into junction polygons
# ============================================================

# -----------------------------
# User settings
# -----------------------------
CITY = "Dresden"

DATA_ROOT = Path(
    r"Z:\_Public\Promotionen\Golpayegani\Paper3\OSM_Network_Simplification\GIS_Data"
)

JUNCTION_BUFFER_METERS = 25
MIN_RELEVANT_CONNECTIONS = 3

# Road classes that count as real street connections
RELEVANT_HIGHWAYS = {
    "motorway",
    "motorway_link",
    "trunk",
    "trunk_link",
    "primary",
    "primary_link",
    "secondary",
    "secondary_link",
    "tertiary",
    "tertiary_link",
    "unclassified",
    "residential",
    "living_street",
}

# Road classes ignored for defining main crash-analysis junctions
# WATCH FOR PEDESTRIAN AND/OR CYCLISTS CRASHES LATER!!!
IGNORED_HIGHWAYS = {
    "footway",
    "path",
    "cycleway",
    "steps",
    "service",
    "track",
    "pedestrian",
    "corridor",
    "bridleway",
}

# -----------------------------
# Input / output folders
# -----------------------------
CITY_DIR = DATA_ROOT / CITY
PROCESSED_DIR = CITY_DIR / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

SEGMENT_GRAPHML = PROCESSED_DIR / f"{CITY.lower()}_segment_network.graphml"
JUNCTION_GPKG = PROCESSED_DIR / f"{CITY.lower()}_junction_areas.gpkg"

print("=" * 60)
print("Creating strict junction areas for crash analysis")
print(f"City: {CITY}")
print(f"Buffer: {JUNCTION_BUFFER_METERS} m")
print(f"Minimum relevant connections: {MIN_RELEVANT_CONNECTIONS}")
print("=" * 60)

if not SEGMENT_GRAPHML.exists():
    raise FileNotFoundError(
        f"Segment GraphML not found:\n{SEGMENT_GRAPHML}\n"
        "Run 01_create_segment_network.py first."
    )

# -----------------------------
# Load segment network
# -----------------------------
print("Loading segment network...")
G_segment = ox.load_graphml(SEGMENT_GRAPHML)

nodes, edges = ox.graph_to_gdfs(G_segment)

nodes = nodes.reset_index()
edges = edges.reset_index()

# -----------------------------
# Helper function
# -----------------------------
def normalize_highway(value):
    """
    OSM highway tags can be strings or lists.
    This function converts them into a clean list of strings.
    """
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        # Sometimes GraphML reloads lists as strings like "['residential', 'service']"
        value = value.strip()
        value = value.replace("[", "").replace("]", "").replace("'", "").replace('"', "")
        return [v.strip() for v in value.split(",")]
    return []


# -----------------------------
# Filter relevant edges
# -----------------------------
print("Filtering relevant road edges...")

edges["highway_list"] = edges["highway"].apply(normalize_highway)

edges["is_relevant_road"] = edges["highway_list"].apply(
    lambda values: any(v in RELEVANT_HIGHWAYS for v in values)
)

relevant_edges = edges[edges["is_relevant_road"]].copy()

print(f"All segment edges: {len(edges):,}")
print(f"Relevant road edges: {len(relevant_edges):,}")

# -----------------------------
# Count relevant connections per node
# -----------------------------
print("Counting relevant connections per node...")

connection_neighbors = {}

for _, row in relevant_edges.iterrows():
    u = row["u"]
    v = row["v"]

    connection_neighbors.setdefault(u, set()).add(v)
    connection_neighbors.setdefault(v, set()).add(u)

connection_counts = {
    node: len(neighbors)
    for node, neighbors in connection_neighbors.items()
}

nodes["relevant_connection_count"] = (
    nodes["osmid"]
    .map(connection_counts)
    .fillna(0)
    .astype(int)
)
# -----------------------------
# Select candidate junction nodes
# -----------------------------
candidate_nodes = nodes[
    nodes["relevant_connection_count"] >= MIN_RELEVANT_CONNECTIONS
].copy()

candidate_nodes["candidate_node_id"] = candidate_nodes.index + 1

print(f"Candidate junction nodes: {len(candidate_nodes):,}")

# -----------------------------
# Create buffers
# -----------------------------
print("Creating buffers around candidate nodes...")

candidate_buffers = candidate_nodes.copy()
candidate_buffers["geometry"] = candidate_buffers.geometry.buffer(JUNCTION_BUFFER_METERS)

# -----------------------------
# Dissolve overlapping buffers
# -----------------------------
print("Dissolving overlapping buffers into junction areas...")

if candidate_buffers.empty:
    raise ValueError("No candidate junction nodes found. Try relaxing the filtering rules.")

dissolved = candidate_buffers.geometry.union_all()

if dissolved.geom_type == "MultiPolygon":
    geometries = list(dissolved.geoms)
else:
    geometries = [dissolved]

junction_areas = gpd.GeoDataFrame(
    geometry=geometries,
    crs=candidate_buffers.crs,
)

junction_areas["junction_id"] = junction_areas.index + 1
junction_areas["buffer_m"] = JUNCTION_BUFFER_METERS
junction_areas["min_relevant_connections"] = MIN_RELEVANT_CONNECTIONS
junction_areas["analysis_level"] = "strict_junction_area"
junction_areas["area_m2"] = junction_areas.geometry.area

print(f"Final junction areas: {len(junction_areas):,}")

# -----------------------------
# Save outputs
# -----------------------------
print("Saving outputs...")

junction_areas.to_file(
    JUNCTION_GPKG,
    layer="junction_areas",
    driver="GPKG",
)

candidate_nodes.to_file(
    JUNCTION_GPKG,
    layer="candidate_junction_nodes",
    driver="GPKG",
)

relevant_edges.to_file(
    JUNCTION_GPKG,
    layer="relevant_road_edges",
    driver="GPKG",
)

print("=" * 60)
print("Done.")
print("Saved to:")
print(f"  {JUNCTION_GPKG}")
print("=" * 60)