from pathlib import Path
from collections import defaultdict

import geopandas as gpd
import pandas as pd
from shapely.ops import unary_union, linemerge

# ============================================================
# 05_create_j2j_detailed_network.py
#
# Purpose:
# Create J2J-Detailed network.
#
# Logic:
# - candidate_junction_nodes are the breakpoints
# - relevant_road_edges are the tiny road pieces
# - tiny edges are merged from one candidate junction node
#   to the next candidate junction node
# - parallel carriageways are kept separate
# ============================================================

CITY = "Dresden"

DATA_ROOT = Path(
    r"C:\Users\Golpayegani\GIS_Data\OSM_Crash_Network"
)

CITY_DIR = DATA_ROOT / CITY
PROCESSED_DIR = CITY_DIR / "processed"
OUTPUT_DIR = CITY_DIR / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

JUNCTION_GPKG = PROCESSED_DIR / f"{CITY.lower()}_junction_areas_strict.gpkg"

OUTPUT_GPKG = PROCESSED_DIR / f"{CITY.lower()}_j2j_detailed_network.gpkg"
MAPPING_CSV = OUTPUT_DIR / f"{CITY.lower()}_relevant_edge_to_j2j_detailed_mapping.csv"


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
    return linemerge(unary_union(geoms))


print("=" * 60)
print("Creating J2J-Detailed network")
print("=" * 60)

print("Loading relevant road edges...")
edges = gpd.read_file(JUNCTION_GPKG, layer="relevant_road_edges")

print("Loading candidate junction nodes...")
candidate_nodes = gpd.read_file(JUNCTION_GPKG, layer="candidate_junction_nodes")

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

# ------------------------------------------------------------
# Build adjacency from relevant road edges
# ------------------------------------------------------------
adjacency = defaultdict(list)

for _, row in edges.iterrows():
    edge_id = int(row["local_edge_id"])
    u = row["u_str"]
    v = row["v_str"]

    adjacency[u].append((edge_id, v))
    adjacency[v].append((edge_id, u))

print(f"Relevant graph nodes: {len(adjacency):,}")

# ------------------------------------------------------------
# Trace paths between candidate junction nodes
# ------------------------------------------------------------
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
            path_nodes.append(current_node)

            if current_node in candidate_node_ids and current_node != start_node:
                end_node = current_node
                end_type = "junction_to_junction"
                break

            if current_node in candidate_node_ids and current_node == start_node:
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
                end_type = "dead_end"
                break

            if len(next_candidates) > 1:
                end_type = "unresolved_branch"
                break

        if not path_edge_ids:
            continue

        path_edges = edges[edges["local_edge_id"].isin(path_edge_ids)].copy()

        geometry = merge_lines(path_edges.geometry)
        if geometry is None:
            continue

        row = {
            "j2j_id": j2j_id,
            "start_node": start_node,
            "end_node": end_node,
            "end_type": end_type,
            "n_source_edges": len(path_edges),
            "source_segment_ids": unique_join(path_edges["segment_id"])
            if "segment_id" in path_edges.columns
            else "",
            "source_edge_ids": unique_join(path_edges["edge_id"])
            if "edge_id" in path_edges.columns
            else "",
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

j2j_edges = gpd.GeoDataFrame(
    j2j_rows,
    geometry="geometry",
    crs=edges.crs,
)

mapping = pd.DataFrame(mapping_rows)

print(f"J2J-Detailed edges created: {len(j2j_edges):,}")

if not j2j_edges.empty:
    print(j2j_edges["end_type"].value_counts())

print("Saving outputs...")

j2j_edges.to_file(
    OUTPUT_GPKG,
    layer="j2j_detailed_edges",
    driver="GPKG",
)

candidate_nodes.to_file(
    OUTPUT_GPKG,
    layer="candidate_junction_nodes",
    driver="GPKG",
)

edges.to_file(
    OUTPUT_GPKG,
    layer="source_relevant_road_edges",
    driver="GPKG",
)

mapping.to_csv(MAPPING_CSV, index=False)

print("=" * 60)
print("Done.")
print(f"Saved J2J-Detailed network:")
print(f"  {OUTPUT_GPKG}")
print(f"Saved mapping table:")
print(f"  {MAPPING_CSV}")
print("=" * 60)