from pathlib import Path

import geopandas as gpd
import pandas as pd

# ============================================================
# 04_create_crash_related_attributes.py
#
# Purpose:
# Add crash-relevant built-environment/network attributes
# to the Level 3A J2J-Detailed network.
#
# Currently computes:
# - access edge count near each J2J edge
# - access edge density per km
# - access node count near each J2J edge
# - access node density per km
# - counts by access type
# ============================================================

CITY = "Dresden"

DATA_ROOT = Path(
    r"Z:\_Public\Promotionen\Golpayegani\Paper3\OSM_Network_Simplification\GIS_Data"
)

CITY_DIR = DATA_ROOT / CITY
PROCESSED_DIR = CITY_DIR / "processed"
OUTPUT_DIR = CITY_DIR / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SEGMENT_GPKG = PROCESSED_DIR / f"{CITY.lower()}_segment_network.gpkg"
J2J_GPKG = PROCESSED_DIR / f"{CITY.lower()}_j2j_detailed_network.gpkg"

OUTPUT_GPKG = PROCESSED_DIR / f"{CITY.lower()}_j2j_detailed_attributes.gpkg"

SEGMENT_EDGES_LAYER = "segment_edges"
J2J_LAYER = "Level 3A: j2j_detailed_network"

ACCESS_BUFFER_M = 8

ACCESS_HIGHWAYS = {
    "service",
    "footway",
    "path",
    "cycleway",
    "pedestrian",
    "living_street",
}

ACCESS_TYPE_GROUPS = {
    "service": {"service"},
    "footway_path": {"footway", "path", "pedestrian"},
    "cycleway": {"cycleway"},
    "living_street": {"living_street"},
}


def normalize_osm_values(value):
    if pd.isna(value):
        return []

    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]

    value = str(value).strip()

    value = (
        value.replace("[", "")
             .replace("]", "")
             .replace("'", "")
             .replace('"', "")
    )

    value = value.replace(";", ",")

    return [v.strip() for v in value.split(",") if v.strip()]


def has_any_highway(value, allowed_values):
    values = normalize_osm_values(value)
    return any(v in allowed_values for v in values)


print("=" * 60)
print("Creating crash-related Level 3A attributes")
print("=" * 60)

print("Loading Level 3A J2J network...")
j2j = gpd.read_file(J2J_GPKG, layer=J2J_LAYER)

print("Loading Level 1 segment edges...")
segment_edges = gpd.read_file(SEGMENT_GPKG, layer=SEGMENT_EDGES_LAYER)

if segment_edges.crs != j2j.crs:
    segment_edges = segment_edges.to_crs(j2j.crs)

# ------------------------------------------------------------
# Filter access edges
# ------------------------------------------------------------

print("Filtering access edges...")

segment_edges["highway_list"] = segment_edges["highway"].apply(normalize_osm_values)

access_edges = segment_edges[
    segment_edges["highway_list"].apply(
        lambda values: any(v in ACCESS_HIGHWAYS for v in values)
    )
].copy()

access_edges = access_edges.reset_index(drop=True)
access_edges["access_edge_id"] = access_edges.index

print(f"All Level 1 segment edges: {len(segment_edges):,}")
print(f"Access edges: {len(access_edges):,}")

# ------------------------------------------------------------
# Create buffered J2J geometries
# ------------------------------------------------------------

print("Creating J2J buffers...")

j2j_buffers = j2j[["j2j_id", "length_m", "geometry"]].copy()
j2j_buffers["geometry"] = j2j_buffers.geometry.buffer(ACCESS_BUFFER_M)

# ------------------------------------------------------------
# Spatial join: access edges within J2J buffer
# ------------------------------------------------------------

print("Counting buffered access edges...")

access_join = gpd.sjoin(
    access_edges,
    j2j_buffers[["j2j_id", "geometry"]],
    how="inner",
    predicate="intersects",
)

# Total access edge count
access_counts = (
    access_join
    .drop_duplicates(subset=["j2j_id", "access_edge_id"])
    .groupby("j2j_id")
    .size()
    .reset_index(name="n_access_edges_buffered")
)

j2j = j2j.merge(access_counts, on="j2j_id", how="left")
j2j["n_access_edges_buffered"] = j2j["n_access_edges_buffered"].fillna(0).astype(int)

j2j["access_edge_density_per_km"] = (
    j2j["n_access_edges_buffered"] / (j2j["length_m"] / 1000)
)

# ------------------------------------------------------------
# Counts by access type
# ------------------------------------------------------------

print("Counting access edges by type...")

for group_name, highway_values in ACCESS_TYPE_GROUPS.items():

    temp = access_join[
        access_join["highway_list"].apply(
            lambda values: any(v in highway_values for v in values)
        )
    ].copy()

    counts = (
        temp
        .drop_duplicates(subset=["j2j_id", "access_edge_id"])
        .groupby("j2j_id")
        .size()
        .reset_index(name=f"n_{group_name}_access_edges")
    )

    j2j = j2j.merge(counts, on="j2j_id", how="left")
    j2j[f"n_{group_name}_access_edges"] = (
        j2j[f"n_{group_name}_access_edges"]
        .fillna(0)
        .astype(int)
    )

    j2j[f"{group_name}_access_density_per_km"] = (
        j2j[f"n_{group_name}_access_edges"] / (j2j["length_m"] / 1000)
    )

# ------------------------------------------------------------
# Access node count
# ------------------------------------------------------------
# This avoids over-counting long access ways split into many small edges.
# It counts unique u/v nodes of access edges near each J2J edge.

print("Counting buffered access nodes...")

u_nodes = access_edges[["u", "geometry"]].copy()
u_nodes["access_node_id"] = access_edges["u"].astype(str)
u_nodes["geometry"] = access_edges.geometry.apply(lambda g: g.interpolate(0))

v_nodes = access_edges[["v", "geometry"]].copy()
v_nodes["access_node_id"] = access_edges["v"].astype(str)
v_nodes["geometry"] = access_edges.geometry.apply(lambda g: g.interpolate(1, normalized=True))

access_nodes = pd.concat(
    [
        u_nodes[["access_node_id", "geometry"]],
        v_nodes[["access_node_id", "geometry"]],
    ],
    ignore_index=True,
)

access_nodes = gpd.GeoDataFrame(
    access_nodes,
    geometry="geometry",
    crs=j2j.crs,
).drop_duplicates(subset=["access_node_id"])

node_join = gpd.sjoin(
    access_nodes,
    j2j_buffers[["j2j_id", "geometry"]],
    how="inner",
    predicate="intersects",
)

node_counts = (
    node_join
    .drop_duplicates(subset=["j2j_id", "access_node_id"])
    .groupby("j2j_id")
    .size()
    .reset_index(name="n_access_nodes_buffered")
)

j2j = j2j.merge(node_counts, on="j2j_id", how="left")
j2j["n_access_nodes_buffered"] = j2j["n_access_nodes_buffered"].fillna(0).astype(int)

j2j["access_node_density_per_km"] = (
    j2j["n_access_nodes_buffered"] / (j2j["length_m"] / 1000)
)
# ------------------------------------------------------------
# Crossing count near each Level 3A edge
# ------------------------------------------------------------
CROSSING_BUFFER_M = 8

crossing_edges = segment_edges[
    (
        segment_edges.get("highway", "").astype(str).str.lower().eq("crossing")
    )
    |
    (
        segment_edges.get("footway", "").astype(str).str.lower().eq("crossing")
    )
].copy()

j2j_crossing_buffers = j2j[["j2j_id", "length_m", "geometry"]].copy()
j2j_crossing_buffers["geometry"] = j2j_crossing_buffers.geometry.buffer(CROSSING_BUFFER_M)

crossing_join = gpd.sjoin(
    crossing_edges,
    j2j_crossing_buffers[["j2j_id", "geometry"]],
    how="inner",
    predicate="intersects",
)

crossing_counts = (
    crossing_join
    .groupby("j2j_id")
    .size()
    .reset_index(name="n_crossing_edges_buffered")
)

j2j = j2j.merge(crossing_counts, on="j2j_id", how="left")
j2j["n_crossing_edges_buffered"] = j2j["n_crossing_edges_buffered"].fillna(0).astype(int)

j2j["crossing_density_per_km"] = (
    j2j["n_crossing_edges_buffered"] / (j2j["length_m"] / 1000)
)
# ------------------------------------------------------------
# Traffic-calming count near each Level 3A edge
# ------------------------------------------------------------
TRAFFIC_CALMING_BUFFER_M = 8

traffic_calming_edges = segment_edges[
    segment_edges.get("traffic_calming", "").astype(str).str.lower().notna()
].copy()

traffic_calming_edges = traffic_calming_edges[
    ~traffic_calming_edges["traffic_calming"].astype(str).str.lower().isin(
        ["", "nan", "none", "no"]
    )
].copy()

traffic_calming_join = gpd.sjoin(
    traffic_calming_edges,
    j2j_crossing_buffers[["j2j_id", "geometry"]],
    how="inner",
    predicate="intersects",
)

traffic_calming_counts = (
    traffic_calming_join
    .groupby("j2j_id")
    .size()
    .reset_index(name="n_traffic_calming_buffered")
)

j2j = j2j.merge(traffic_calming_counts, on="j2j_id", how="left")
j2j["n_traffic_calming_buffered"] = j2j["n_traffic_calming_buffered"].fillna(0).astype(int)

j2j["traffic_calming_density_per_km"] = (
    j2j["n_traffic_calming_buffered"] / (j2j["length_m"] / 1000)
)
# ------------------------------------------------------------
# Tram / PT way proximity
# ------------------------------------------------------------
PT_BUFFER_M = 8

pt_edges = segment_edges[
    segment_edges.get("railway", "").astype(str).str.lower().isin(
        ["tram", "light_rail"]
    )
].copy()

pt_join = gpd.sjoin(
    pt_edges,
    j2j_crossing_buffers[["j2j_id", "geometry"]],
    how="inner",
    predicate="intersects",
)

pt_counts = (
    pt_join
    .groupby("j2j_id")
    .size()
    .reset_index(name="n_tram_edges_buffered")
)

j2j = j2j.merge(pt_counts, on="j2j_id", how="left")
j2j["n_tram_edges_buffered"] = j2j["n_tram_edges_buffered"].fillna(0).astype(int)

j2j["tram_edge_density_per_km"] = (
    j2j["n_tram_edges_buffered"] / (j2j["length_m"] / 1000)
)

# ------------------------------------------------------------
# Save output
# ------------------------------------------------------------

if OUTPUT_GPKG.exists():
    print("Removing old output GeoPackage...")
    OUTPUT_GPKG.unlink()

print("Saving enriched Level 3A network...")

j2j.to_file(
    OUTPUT_GPKG,
    layer="Level 3A: j2j_detailed_network_attributes",
    driver="GPKG",
)

print("=" * 60)
print("Done.")
print(f"Saved:")
print(f"  {OUTPUT_GPKG}")
print("=" * 60)