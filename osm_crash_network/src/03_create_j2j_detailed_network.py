from pathlib import Path
from collections import defaultdict

import geopandas as gpd
import pandas as pd
from shapely.ops import unary_union, linemerge

# ============================================================
# 03_create_j2j_detailed_network.py
#
# Level 3A: J2J-Detailed Network
#
# Inputs:
# - Level 1 segment_nodes
# - Level 2 relevant_road_edges
# - Level 2 junction_areas
#
# Purpose:
# Merge tiny relevant road edges into longer edges from one
# junction area to the next junction area.
#
# Main rule:
# Junction areas are the main breakpoints.
# Intermediate graph nodes are NOT breakpoints.
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
INTERSECTION_GPKG = PROCESSED_DIR / f"{CITY.lower()}_intersection_network.gpkg"

OUTPUT_GPKG = PROCESSED_DIR / f"{CITY.lower()}_j2j_detailed_network.gpkg"
MAPPING_CSV = OUTPUT_DIR / f"{CITY.lower()}_j2j_detailed_mapping.csv"
EDGE_USAGE_CSV = OUTPUT_DIR / f"{CITY.lower()}_j2j_source_edge_usage.csv"

SEGMENT_NODES_LAYER = "segment_nodes"
RELEVANT_EDGES_LAYER = "relevant_road_edges"
JUNCTION_AREAS_LAYER = "junction_areas"


def unique_join(values):
    clean = []
    for v in values:
        if pd.isna(v):
            continue
        clean.append(str(v))
    return ";".join(sorted(set(clean)))


def merge_lines(geometries):
    geoms = [g for g in geometries if g is not None and not g.is_empty]

    if not geoms:
        return None

    if len(geoms) == 1:
        return geoms[0]

    merged = unary_union(geoms)

    if merged.geom_type == "LineString":
        return merged

    return linemerge(merged)


def is_junction_supernode(node_id):
    return str(node_id).startswith("JUNCTION_")


print("=" * 60)
print("Creating Level 3A: J2J-Detailed Network")
print("=" * 60)

# ============================================================
# 1. Load input data
# ============================================================

print("Loading Level 1 segment nodes...")
nodes = gpd.read_file(
    SEGMENT_GPKG,
    layer=SEGMENT_NODES_LAYER,
)

print("Loading Level 2 relevant road edges...")
edges = gpd.read_file(
    INTERSECTION_GPKG,
    layer=RELEVANT_EDGES_LAYER,
)

print("Loading Level 2 junction areas...")
junctions = gpd.read_file(
    INTERSECTION_GPKG,
    layer=JUNCTION_AREAS_LAYER,
)

if nodes.crs != edges.crs:
    nodes = nodes.to_crs(edges.crs)

if junctions.crs != edges.crs:
    junctions = junctions.to_crs(edges.crs)

nodes["node_id_str"] = nodes["osmid"].astype(str)

edges = edges.reset_index(drop=True)
edges["local_edge_id"] = edges.index
edges["u_str"] = edges["u"].astype(str)
edges["v_str"] = edges["v"].astype(str)

print(f"Segment nodes: {len(nodes):,}")
print(f"Relevant road edges: {len(edges):,}")
print(f"Junction areas: {len(junctions):,}")

# ============================================================
# 2. Find which segment nodes are inside junction areas
# ============================================================

print("Assigning segment nodes to junction areas...")

nodes_in_junctions = gpd.sjoin(
    nodes[["node_id_str", "geometry"]],
    junctions[["junction_id", "geometry"]],
    how="left",
    predicate="intersects",
)

node_to_junction = (
    nodes_in_junctions
    .dropna(subset=["junction_id"])
    .drop_duplicates(subset=["node_id_str"])
    .set_index("node_id_str")["junction_id"]
    .astype(int)
    .to_dict()
)

print(f"Segment nodes inside junction areas: {len(node_to_junction):,}")

# ============================================================
# 3. Contract junction areas into supernodes
# ============================================================

def contracted_node(node_id):
    if node_id in node_to_junction:
        return f"JUNCTION_{node_to_junction[node_id]}"
    return node_id


edges["cu"] = edges["u_str"].apply(contracted_node)
edges["cv"] = edges["v_str"].apply(contracted_node)

# Remove edges fully inside the same junction area
between_edges = edges[edges["cu"] != edges["cv"]].copy()

print(f"Edges after removing internal junction edges: {len(between_edges):,}")

# ============================================================
# 4. Build adjacency list
# ============================================================

print("Building contracted adjacency list...")

adjacency = defaultdict(list)

for _, row in between_edges.iterrows():
    edge_id = int(row["local_edge_id"])
    u = row["cu"]
    v = row["cv"]

    adjacency[u].append((edge_id, v))
    adjacency[v].append((edge_id, u))

junction_supernodes = {
    node for node in adjacency
    if is_junction_supernode(node)
}

print(f"Contracted graph nodes: {len(adjacency):,}")
print(f"Junction supernodes: {len(junction_supernodes):,}")

# ============================================================
# 5. Trace from junction area to next junction area / dead end
# ============================================================

print("Tracing J2J-Detailed paths...")

j2j_rows = []
mapping_rows = []
j2j_id = 1

visited_start_edge_pairs = set()

for start_junction in junction_supernodes:

    for first_edge_id, next_node in adjacency[start_junction]:

        pair_key = (start_junction, first_edge_id)

        if pair_key in visited_start_edge_pairs:
            continue

        visited_start_edge_pairs.add(pair_key)

        stack = [
            (
                start_junction,
                next_node,
                start_junction,
                [first_edge_id],
                [start_junction, next_node],
            )
        ]

        while stack:

            start_node, current_node, previous_node, path_edge_ids, path_nodes = stack.pop()

            if (
                is_junction_supernode(current_node)
                and current_node != start_node
            ):
                end_node = current_node
                end_type = "junction_to_junction"

            else:
                next_options = [
                    (eid, nbr)
                    for eid, nbr in adjacency[current_node]
                    if nbr != previous_node and eid not in path_edge_ids
                ]

                if len(next_options) == 0:
                    end_node = current_node
                    end_type = "junction_to_dead_end"

                elif len(next_options) == 1:
                    next_edge_id, next_node = next_options[0]

                    stack.append(
                        (
                            start_node,
                            next_node,
                            current_node,
                            path_edge_ids + [next_edge_id],
                            path_nodes + [next_node],
                        )
                    )
                    continue

                else:
                    # Branch: follow every possible continuation separately
                    for next_edge_id, next_node in next_options:
                        stack.append(
                            (
                                start_node,
                                next_node,
                                current_node,
                                path_edge_ids + [next_edge_id],
                                path_nodes + [next_node],
                            )
                        )
                    continue

            path_edges = between_edges[
                between_edges["local_edge_id"].isin(path_edge_ids)
            ].copy()

            geometry = merge_lines(path_edges.geometry)

            if geometry is None or geometry.is_empty:
                continue

            row = {
                "j2j_id": j2j_id,
                "start_node": start_node,
                "end_node": end_node,
                "end_type": end_type,
                "n_source_edges": len(path_edges),
                "source_local_edge_ids": unique_join(path_edges["local_edge_id"]),
                "source_segment_ids": unique_join(path_edges["segment_id"])
                if "segment_id" in path_edges.columns else "",
                "source_edge_ids": unique_join(path_edges["edge_id"])
                if "edge_id" in path_edges.columns else "",
                "path_nodes": ";".join(map(str, path_nodes)),
                "length_m": path_edges.geometry.length.sum(),
                "geometry": geometry,
            }

            for col in [
                "name",
                "highway",
                "oneway",
                "maxspeed",
                "lanes",
                "sidewalk",
                "sidewalk:left",
                "sidewalk:right",
                "cycleway",
                "cycleway:left",
                "cycleway:right",
                "surface",
                "lit",
                "bridge",
                "tunnel",
            ]:
                if col in path_edges.columns:
                    row[f"{col}_values"] = unique_join(path_edges[col])

            row["has_sidewalk"] = (
                any(
                    str(v).lower() not in ["nan", "none", "no", ""]
                    for v in path_edges["sidewalk"]
                )
                if "sidewalk" in path_edges.columns
                else False
            )

            row["has_cycleway"] = (
                any(
                    str(v).lower() not in ["nan", "none", "no", ""]
                    for v in path_edges["cycleway"]
                )
                if "cycleway" in path_edges.columns
                else False
            )

            j2j_rows.append(row)

            for _, src in path_edges.iterrows():
                mapping_rows.append(
                    {
                        "j2j_id": j2j_id,
                        "source_local_edge_id": src["local_edge_id"],
                        "segment_id": src["segment_id"] if "segment_id" in src else None,
                        "edge_id": src["edge_id"] if "edge_id" in src else None,
                        "start_node": start_node,
                        "end_node": end_node,
                        "end_type": end_type,
                    }
                )

            j2j_id += 1

# ============================================================
# 6. Create outputs
# ============================================================

j2j_edges = gpd.GeoDataFrame(
    j2j_rows,
    geometry="geometry",
    crs=edges.crs,
)

mapping = pd.DataFrame(mapping_rows)

print(f"Level 3A J2J-Detailed edges created: {len(j2j_edges):,}")

if not j2j_edges.empty:
    print("\nEnd type summary:")
    print(j2j_edges["end_type"].value_counts())

# ============================================================
# 7. Diagnostic: source edge usage
# ============================================================

if not mapping.empty:
    edge_usage = (
        mapping.groupby("source_local_edge_id")
        .size()
        .reset_index(name="n_j2j_edges_using_source")
    )

    repeated_source_edges = edge_usage[
        edge_usage["n_j2j_edges_using_source"] > 1
    ].copy()

    print(
        f"Source edges reused in multiple J2J paths: "
        f"{len(repeated_source_edges):,}"
    )
else:
    edge_usage = pd.DataFrame()
    repeated_source_edges = pd.DataFrame()

# ============================================================
# 8. Save outputs
# ============================================================

print("Saving outputs...")

j2j_edges.to_file(
    OUTPUT_GPKG,
    layer="Level 3A: j2j_detailed_network",
    driver="GPKG",
)

mapping.to_csv(MAPPING_CSV, index=False)

edge_usage.to_csv(
    EDGE_USAGE_CSV,
    index=False,
)

if not repeated_source_edges.empty:
    repeated_edges_layer = between_edges.merge(
        repeated_source_edges,
        left_on="local_edge_id",
        right_on="source_local_edge_id",
        how="inner",
    )

    repeated_edges_layer.to_file(
        OUTPUT_GPKG,
        layer="Level 3A: repeated_source_edges",
        driver="GPKG",
    )

print("=" * 60)
print("Done.")
print(f"Saved J2J-Detailed network:")
print(f"  {OUTPUT_GPKG}")
print(f"Saved mapping table:")
print(f"  {MAPPING_CSV}")
print("=" * 60)