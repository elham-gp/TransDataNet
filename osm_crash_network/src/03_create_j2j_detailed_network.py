from pathlib import Path

import geopandas as gpd
import pandas as pd
import networkx as nx
from shapely.ops import unary_union, linemerge

# ============================================================
# 03_create_j2j_detailed_network.py
#
# Level 3A: J2J-Detailed Network
#
# Component-based logic:
# 1. Load Level 1 segment_nodes.
# 2. Load Level 2 relevant_road_edges and junction_areas.
# 3. Contract nodes inside junction areas into JUNCTION_x supernodes.
# 4. Remove edges fully inside one junction area.
# 5. Build connected components from non-junction edges.
# 6. Add boundary edges back to each component.
# 7. Merge component edges into Level 3A edges.
#
# Outputs:
# - Level 3A: j2j_detailed_network
# - Level 3A: problem_edges
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
INTERSECTION_GPKG = PROCESSED_DIR / f"{CITY.lower()}_junction_areas.gpkg"

OUTPUT_GPKG = PROCESSED_DIR / f"{CITY.lower()}_j2j_detailed_network.gpkg"
MAPPING_CSV = OUTPUT_DIR / f"{CITY.lower()}_j2j_detailed_mapping.csv"

SEGMENT_NODES_LAYER = "segment_nodes"
RELEVANT_EDGES_LAYER = "relevant_road_edges"
JUNCTION_AREAS_LAYER = "junction_areas"


def unique_join(values):
    vals = []
    for v in values:
        if pd.isna(v):
            continue
        vals.append(str(v))
    return ";".join(sorted(set(vals)))


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


def is_junction_node(node):
    return str(node).startswith("JUNCTION_")


def build_output_row(j2j_id, group, edge_type, start_junction_id, end_junction_id):
    geometry = merge_lines(group.geometry)

    if geometry is None or geometry.is_empty:
        return None

    row = {
        "j2j_id": j2j_id,
        "edge_type": edge_type,
        "start_junction_id": start_junction_id,
        "end_junction_id": end_junction_id,
        "n_source_edges": len(group),
        "source_edge_ids": unique_join(group["source_edge_id"]),
        "length_m": group.geometry.length.sum(),
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
        if col in group.columns:
            row[f"{col}_values"] = unique_join(group[col])

    row["has_sidewalk"] = (
        any(str(v).lower() not in ["nan", "none", "no", ""] for v in group["sidewalk"])
        if "sidewalk" in group.columns
        else False
    )

    row["has_cycleway"] = (
        any(str(v).lower() not in ["nan", "none", "no", ""] for v in group["cycleway"])
        if "cycleway" in group.columns
        else False
    )

    return row


print("=" * 60)
print("Creating Level 3A: J2J-Detailed Network")
print("=" * 60)

# Load inputs
nodes = gpd.read_file(SEGMENT_GPKG, layer=SEGMENT_NODES_LAYER)
edges = gpd.read_file(INTERSECTION_GPKG, layer=RELEVANT_EDGES_LAYER)
junctions = gpd.read_file(INTERSECTION_GPKG, layer=JUNCTION_AREAS_LAYER)

if nodes.crs != edges.crs:
    nodes = nodes.to_crs(edges.crs)

if junctions.crs != edges.crs:
    junctions = junctions.to_crs(edges.crs)

nodes["node_id_str"] = nodes["osmid"].astype(str)

edges = edges.reset_index(drop=True)
edges["source_edge_id"] = edges.index
edges["u_str"] = edges["u"].astype(str)
edges["v_str"] = edges["v"].astype(str)

print(f"Segment nodes: {len(nodes):,}")
print(f"Relevant road edges: {len(edges):,}")
print(f"Junction areas: {len(junctions):,}")

# Assign segment nodes to junction areas
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


def contract_node(node_id):
    if node_id in node_to_junction:
        return f"JUNCTION_{node_to_junction[node_id]}"
    return node_id


# Contract endpoints
edges["cu"] = edges["u_str"].apply(contract_node)
edges["cv"] = edges["v_str"].apply(contract_node)

# Remove edges fully inside same junction
internal_junction_edges = edges[edges["cu"] == edges["cv"]].copy()
work_edges = edges[edges["cu"] != edges["cv"]].copy()

print(f"Internal junction edges removed: {len(internal_junction_edges):,}")
print(f"Edges used for Level 3A: {len(work_edges):,}")

# Split edge groups
work_edges["cu_is_junction"] = work_edges["cu"].apply(is_junction_node)
work_edges["cv_is_junction"] = work_edges["cv"].apply(is_junction_node)

direct_junction_edges = work_edges[
    work_edges["cu_is_junction"] & work_edges["cv_is_junction"]
].copy()

nonjunction_edges = work_edges[
    ~work_edges["cu_is_junction"] & ~work_edges["cv_is_junction"]
].copy()

boundary_edges = work_edges[
    work_edges["cu_is_junction"] ^ work_edges["cv_is_junction"]
].copy()

print(f"Direct junction-to-junction edges: {len(direct_junction_edges):,}")
print(f"Non-junction edges: {len(nonjunction_edges):,}")
print(f"Boundary edges: {len(boundary_edges):,}")

# Build graph from non-junction edges
G = nx.Graph()

for _, row in nonjunction_edges.iterrows():
    G.add_edge(
        row["cu"],
        row["cv"],
        source_edge_id=int(row["source_edge_id"]),
    )

components = list(nx.connected_components(G))
print(f"Non-junction connected components: {len(components):,}")

# Create outputs
j2j_rows = []
mapping_rows = []
j2j_id = 1

# Direct junction-to-junction edges
if not direct_junction_edges.empty:
    direct_junction_edges["junction_pair"] = direct_junction_edges.apply(
        lambda r: "_".join(
            sorted([
                str(r["cu"]).replace("JUNCTION_", ""),
                str(r["cv"]).replace("JUNCTION_", ""),
            ])
        ),
        axis=1,
    )

    for _, group in direct_junction_edges.groupby("junction_pair"):
        touched = sorted(
            set(
                int(str(v).replace("JUNCTION_", ""))
                for v in list(group["cu"]) + list(group["cv"])
            )
        )

        if len(touched) < 2:
            continue

        start_junction_id = touched[0]
        end_junction_id = touched[1]

        row = build_output_row(
            j2j_id,
            group,
            "junction_to_junction",
            start_junction_id,
            end_junction_id,
        )

        if row is None:
            continue

        j2j_rows.append(row)

        for _, src in group.iterrows():
            mapping_rows.append(
                {
                    "j2j_id": j2j_id,
                    "source_edge_id": src["source_edge_id"],
                    "edge_type": "junction_to_junction",
                    "start_junction_id": start_junction_id,
                    "end_junction_id": end_junction_id,
                }
            )

        j2j_id += 1

# Components outside junctions + boundary edges
for component_id, component_nodes in enumerate(components, start=1):

    component_internal_edges = nonjunction_edges[
        nonjunction_edges["cu"].isin(component_nodes)
        & nonjunction_edges["cv"].isin(component_nodes)
    ].copy()

    component_boundary_edges = boundary_edges[
        boundary_edges["cu"].isin(component_nodes)
        | boundary_edges["cv"].isin(component_nodes)
    ].copy()

    group = pd.concat(
        [component_internal_edges, component_boundary_edges],
        ignore_index=True,
    )

    if group.empty:
        continue

    touched_junctions = []

    for _, r in component_boundary_edges.iterrows():
        if is_junction_node(r["cu"]):
            touched_junctions.append(int(str(r["cu"]).replace("JUNCTION_", "")))
        if is_junction_node(r["cv"]):
            touched_junctions.append(int(str(r["cv"]).replace("JUNCTION_", "")))

    touched_junctions = sorted(set(touched_junctions))

    if len(touched_junctions) >= 2:
        edge_type = "junction_to_junction"
        start_junction_id = touched_junctions[0]
        end_junction_id = touched_junctions[1]

        if len(touched_junctions) > 2:
            edge_type = "multi_junction_component"

    elif len(touched_junctions) == 1:
        edge_type = "junction_to_dead_end"
        start_junction_id = touched_junctions[0]
        end_junction_id = None

    else:
        edge_type = "orphan_component"
        start_junction_id = None
        end_junction_id = None

    row = build_output_row(
        j2j_id,
        group,
        edge_type,
        start_junction_id,
        end_junction_id,
    )

    if row is None:
        continue

    row["component_id"] = component_id
    row["n_touched_junctions"] = len(touched_junctions)
    row["touched_junction_ids"] = unique_join(touched_junctions)

    j2j_rows.append(row)

    for _, src in group.iterrows():
        mapping_rows.append(
            {
                "j2j_id": j2j_id,
                "component_id": component_id,
                "source_edge_id": src["source_edge_id"],
                "edge_type": edge_type,
                "start_junction_id": start_junction_id,
                "end_junction_id": end_junction_id,
            }
        )

    j2j_id += 1

# Final layers
j2j_edges = gpd.GeoDataFrame(
    j2j_rows,
    geometry="geometry",
    crs=edges.crs,
)

mapping = pd.DataFrame(mapping_rows)

valid_types = ["junction_to_junction", "junction_to_dead_end"]
problem_types = ["multi_junction_component", "orphan_component"]

clean_network = j2j_edges[
    j2j_edges["edge_type"].isin(valid_types)
].copy()

problem_edges = j2j_edges[
    j2j_edges["edge_type"].isin(problem_types)
].copy()

total_clean = len(clean_network)
total_problem = len(problem_edges)
total_output = total_clean + total_problem
problem_share = total_problem / total_output * 100 if total_output > 0 else 0

print("=" * 60)
print("Level 3A quality summary")
print("=" * 60)
print(f"Clean network edges: {total_clean:,}")
print(f"Problem edges: {total_problem:,}")
print(f"Problem share: {problem_share:.2f}%")

if not j2j_edges.empty:
    print("\nEdge type summary:")
    print(j2j_edges["edge_type"].value_counts())

# Save only two layers
if OUTPUT_GPKG.exists():
    print("Removing old output GeoPackage...")
    OUTPUT_GPKG.unlink()

clean_network.to_file(
    OUTPUT_GPKG,
    layer="Level 3A: j2j_detailed_network",
    driver="GPKG",
)

problem_edges.to_file(
    OUTPUT_GPKG,
    layer="Level 3A: problem_edges",
    driver="GPKG",
)

mapping.to_csv(MAPPING_CSV, index=False)

print("=" * 60)
print("Done.")
print(f"Saved:")
print(f"  {OUTPUT_GPKG}")
print("=" * 60)