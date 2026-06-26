from pathlib import Path
from collections import defaultdict

import geopandas as gpd
import pandas as pd
from shapely.ops import unary_union, linemerge

# ============================================================
# 03_create_j2j_detailed_network.py
#
# Creates Level 3A: J2J-Detailed Network
#
# Logic:
# - candidate_junction_nodes are breakpoints
# - relevant_road_edges are the source road links
# - tiny relevant edges are traced and merged from one candidate
#   junction node to the next
# - parallel carriageways are preserved
# - dead ends are kept as junction_to_dead_end
# - unresolved branches are counted and saved for inspection
# ============================================================

CITY = "Dresden"

DATA_ROOT = Path(
    r"Z:\_Public\Promotionen\Golpayegani\Paper3\OSM_Network_Simplification\GIS_Data"
)

CITY_DIR = DATA_ROOT / CITY
PROCESSED_DIR = CITY_DIR / "processed"
OUTPUT_DIR = CITY_DIR / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

JUNCTION_GPKG = PROCESSED_DIR / f"{CITY.lower()}_junction_areas.gpkg"

CANDIDATE_NODES_LAYER = "Level 2: dresden_junction_areas — candidate_junction_nodes"
RELEVANT_EDGES_LAYER = "Level 2: dresden_junction_areas — relevant_road_edges"

OUTPUT_GPKG = PROCESSED_DIR / f"{CITY.lower()}_j2j_detailed_network.gpkg"
MAPPING_CSV = OUTPUT_DIR / f"{CITY.lower()}_relevant_edge_to_j2j_detailed_mapping.csv"


def unique_join(values):
    clean = [str(v) for v in values if not pd.isna(v)]
    return ";".join(sorted(set(clean)))


def merge_lines(geometries):
    geoms = [g for g in geometries if g is not None and not g.is_empty]

    return None if not geoms else linemerge(unary_union(geoms))


print("=" * 60)
print("Creating Level 3A: J2J-Detailed Network")
print("=" * 60)

# ============================================================
# Load inputs
# ============================================================

print("Loading candidate junction nodes...")
candidate_nodes = gpd.read_file(
    JUNCTION_GPKG,
    layer=CANDIDATE_NODES_LAYER,
)

print("Loading relevant road edges...")
edges = gpd.read_file(
    JUNCTION_GPKG,
    layer=RELEVANT_EDGES_LAYER,
)

if edges.crs != candidate_nodes.crs:
    candidate_nodes = candidate_nodes.to_crs(edges.crs)

edges = edges.reset_index(drop=True)
edges["local_edge_id"] = edges.index

edges["u_str"] = edges["u"].astype(str)
edges["v_str"] = edges["v"].astype(str)

candidate_nodes["node_osmid_str"] = candidate_nodes["osmid"].astype(str)
candidate_node_ids = set(candidate_nodes["node_osmid_str"])

print(f"Relevant road edges: {len(edges):,}")
print(f"Candidate junction nodes: {len(candidate_nodes):,}")

# ============================================================
# Build adjacency list
# ============================================================

print("Building adjacency list...")

adjacency = defaultdict(list)

for _, row in edges.iterrows():
    edge_id = int(row["local_edge_id"])
    u = row["u_str"]
    v = row["v_str"]

    adjacency[u].append((edge_id, v))
    adjacency[v].append((edge_id, u))

print(f"Relevant graph nodes: {len(adjacency):,}")

# ============================================================
# Trace J2J paths
# ============================================================

print("Tracing paths between candidate junction nodes...")

visited_edges = set()
j2j_rows = []
mapping_rows = []

j2j_id = 1

for start_node in candidate_node_ids:

    if start_node not in adjacency:
        continue

    for first_edge_id, next_node in adjacency[start_node]:

        if first_edge_id in visited_edges:
            continue

        path_edge_ids = []
        path_nodes = [start_node]

        previous_node = start_node
        current_node = next_node
        current_edge_id = first_edge_id

        end_node = None
        end_type = "unknown"

        while True:

            if current_edge_id in visited_edges:
                break

            visited_edges.add(current_edge_id)
            path_edge_ids.append(current_edge_id)
# sourcery skip: while-guard-to-condition
            path_nodes.append(current_node)

            if current_node in candidate_node_ids:
                if current_node != start_node:
                    end_node = current_node
                    end_type = "junction_to_junction"
                    break

                end_node = current_node
                end_type = "same_junction_loop"
                break

            next_candidates = [
                (eid, nbr)
                for eid, nbr in adjacency[current_node]
                if eid not in visited_edges and nbr != previous_node
            ]

            if len(next_candidates) == 1:
                previous_node = current_node
                current_edge_id, current_node = next_candidates[0]
                continue

            if len(next_candidates) == 0:
                end_node = current_node
                end_type = "junction_to_dead_end"
                break

            if len(next_candidates) > 1:
                end_node = current_node
                end_type = "unresolved_branch"
                break

        if not path_edge_ids:
            continue

        path_edges = edges[
            edges["local_edge_id"].isin(path_edge_ids)
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
            "source_segment_ids": unique_join(path_edges["segment_id"])
            if "segment_id" in path_edges.columns else "",
            "source_edge_ids": unique_join(path_edges["edge_id"])
            if "edge_id" in path_edges.columns else "",
            "source_local_edge_ids": unique_join(path_edges["local_edge_id"]),
            "path_nodes": ";".join(path_nodes),
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
# Create outputs
# ============================================================

j2j_edges = gpd.GeoDataFrame(
    j2j_rows,
    geometry="geometry",
    crs=edges.crs,
)

mapping = pd.DataFrame(mapping_rows)

print(f"J2J-Detailed edges created: {len(j2j_edges):,}")

if not j2j_edges.empty:
    print("\nEnd type summary:")
    print(j2j_edges["end_type"].value_counts())

    total_edges = len(j2j_edges)
    unresolved_count = (j2j_edges["end_type"] == "unresolved_branch").sum()
    dead_end_count = (j2j_edges["end_type"] == "junction_to_dead_end").sum()
    j2j_count = (j2j_edges["end_type"] == "junction_to_junction").sum()
    same_loop_count = (j2j_edges["end_type"] == "same_junction_loop").sum()

    print("\nQuality check:")
    print(f"  Total J2J-Detailed edges: {total_edges:,}")
    print(f"  Junction-to-junction edges: {j2j_count:,}")
    print(f"  Junction-to-dead-end edges: {dead_end_count:,}")
    print(f"  Same-junction loops: {same_loop_count:,}")
    print(f"  Unresolved branches: {unresolved_count:,}")
    print(f"  Unresolved branch share: {unresolved_count / total_edges * 100:.2f}%")

# ============================================================
# Save outputs
# ============================================================

print("\nSaving outputs...")

j2j_edges.to_file(
    OUTPUT_GPKG,
    layer="Level 3A: j2j_detailed_edges",
    driver="GPKG",
)

candidate_nodes.to_file(
    OUTPUT_GPKG,
    layer="Level 3A: candidate_junction_nodes",
    driver="GPKG",
)

edges.to_file(
    OUTPUT_GPKG,
    layer="Level 3A: source_relevant_road_edges",
    driver="GPKG",
)

if not j2j_edges.empty:
    unresolved_branches = j2j_edges[
        j2j_edges["end_type"] == "unresolved_branch"
    ].copy()

    if not unresolved_branches.empty:
        unresolved_branches.to_file(
            OUTPUT_GPKG,
            layer="Level 3A: unresolved_branches",
            driver="GPKG",
        )

    dead_end_edges = j2j_edges[
        j2j_edges["end_type"] == "junction_to_dead_end"
    ].copy()

    if not dead_end_edges.empty:
        dead_end_edges.to_file(
            OUTPUT_GPKG,
            layer="Level 3A: junction_to_dead_end_edges",
            driver="GPKG",
        )

mapping.to_csv(MAPPING_CSV, index=False)

print("=" * 60)
print("Done.")
print(f"Saved J2J-Detailed network:")
print(f"  {OUTPUT_GPKG}")
print("Saved mapping table:")
print(f"  {MAPPING_CSV}")
print("=" * 60)