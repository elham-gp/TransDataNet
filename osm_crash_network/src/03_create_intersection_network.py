from pathlib import Path
import osmnx as ox
import geopandas as gpd

# ============================================================
# 03_create_intersection_network.py
#
# Purpose:
# Load the segment network created by script 02 and create a
# consolidated intersection layer for intersection crash analysis.
#
# Output:
#   GeoPackage with consolidated intersection points/polygons
# ============================================================

# -----------------------------
# User settings
# -----------------------------
CITY = "Dresden"

DATA_ROOT = Path(
    r"Z:\_Public\Promotionen\Golpayegani\Paper3\OSM_Network_Simplification\GIS_Data"
)

# Try values such as 15, 20, 25, or 30 meters.
# Larger values merge more nearby OSM nodes into one junction.
TOLERANCE_METERS = 20

# -----------------------------
# Input / output folders
# -----------------------------
CITY_DIR = DATA_ROOT / CITY
PROCESSED_DIR = CITY_DIR / "processed"

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# -----------------------------
# Input / output files
# -----------------------------
SEGMENT_GRAPHML = PROCESSED_DIR / f"{CITY.lower()}_segment_network.graphml"

INTERSECTION_GPKG = PROCESSED_DIR / f"{CITY.lower()}_intersection_network.gpkg"

# -----------------------------
# Load segment graph
# -----------------------------
print("=" * 60)
print("Creating consolidated intersection network")
print(f"City: {CITY}")
print(f"Tolerance: {TOLERANCE_METERS} m")
print("=" * 60)

if not SEGMENT_GRAPHML.exists():
    raise FileNotFoundError(
        f"Segment GraphML not found:\n{SEGMENT_GRAPHML}\n"
        "Run 02_create_segment_network.py first."
    )

print("Loading segment network...")
G_segment = ox.load_graphml(SEGMENT_GRAPHML)

print(f"Segment graph:")
print(f"  Nodes: {len(G_segment.nodes):,}")
print(f"  Edges: {len(G_segment.edges):,}")

# -----------------------------
# Create consolidated intersections
# -----------------------------
print("Consolidating nearby intersection nodes...")

intersections = ox.consolidate_intersections(
    G_segment,
    tolerance=TOLERANCE_METERS,
    rebuild_graph=False,
    dead_ends=False,
)

# Convert GeoSeries -> GeoDataFrame
intersections = gpd.GeoDataFrame(
    geometry=intersections,
    crs=G_segment.graph["crs"]
)

intersections["junction_id"] = intersections.index + 1
intersections["tolerance_m"] = TOLERANCE_METERS
intersections["analysis_level"] = "intersection"

print(f"Consolidated intersections: {len(intersections):,}")

print(type(intersections))
print(intersections.head())

# -----------------------------
# Save GeoPackage
# -----------------------------
print("Saving intersection GeoPackage...")

intersections.to_file(
    INTERSECTION_GPKG,
    layer="consolidated_intersections",
    driver="GPKG",
)

print("=" * 60)
print("Done.")
print(f"Intersection GeoPackage saved to:")
print(f"  {INTERSECTION_GPKG}")
print("=" * 60)