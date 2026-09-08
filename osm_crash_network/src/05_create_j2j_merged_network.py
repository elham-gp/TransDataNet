from pathlib import Path
from itertools import combinations # generates every possible pair of edges within the same junction pair
import math

import geopandas as gpd
import networkx as nx
import pandas as pd
from shapely.geometry import LineString , MultiLineString # creates Level 4 centerlines. stores tested pairs in the diagnostics layer.
from shapely.ops import linemerge # tries to convert multipart lines into a single line.


# ============================================================
# 05_create_unified_street_network.py
#
# Level 4: Unified Street Network
#
# Purpose:
# Merge parallel carriageways in the Level 3A J2J-Detailed
# network into one logical street centerline.
#
# Main logic:
# 1. Only compare J2J edges connecting the same junction pair.
# 2. Test whether they are geometrically parallel and nearby.
# 3. Select the best one-to-one carriageway pairs.
# 4. Build a centerline midway between each selected pair.
# 5. Keep all unmatched Level 3A edges unchanged.
#
# Outputs:
# - Level 4: unified_street_network
# - Level 4: parallel_pair_diagnostics
# - CSV mapping Level 3A edges to Level 4 edges
# ============================================================


# ============================================================
# 1. User settings
# ============================================================

CITY = "Dresden"

DATA_ROOT = Path(
    r"Z:\_Public\Promotionen\Golpayegani\Paper3"
    r"\OSM_Network_Simplification\GIS_Data"
)

# Parallel-carriageway detection thresholds
# length_ratio =shorter edge / longer edge
MIN_LENGTH_RATIO_J2J = 0.65 # The shorter candidate edge must be at least 65% as long as the longer edge.
MIN_LENGTH_RATIO_J2D = 0.45 

MAX_MEAN_SEPARATION_M = 40 # The average distance between corresponding points on the two edges must be at most 18 m.
MAX_POINT_SEPARATION_M = 50 # No corresponding sampled point should be farther than 32 m. This protects against cases where two lines are close for most of their length but diverge significantly at one end.

MIN_PARALLEL_OVERLAP_FRACTION = 0.70 # At least 70% of both lines must run within the permitted distance of the other line.

# Number of normalized sample locations used to:
# - compare carriageways;
# - construct the midpoint centerline.
N_COMPARISON_POINTS = 25 # positions when comparing geometry
N_CENTERLINE_POINTS = 50
MAX_PARALLEL_DISTANCE_M = 45 # When calculating overlap, a sampled point counts as being close to the opposite carriageway if its distance to that line is at most 45 m.
# mutual proximity
MIN_PARALLEL_OVERLAP_J2J = 0.70
MIN_PARALLEL_OVERLAP_J2D = 0.55

# Attribute compatibility rules
# Missing information does not cause rejection.
REQUIRE_NAME_MATCH_WHEN_AVAILABLE = True # their names must overlap
REQUIRE_HIGHWAY_OVERLAP_WHEN_AVAILABLE = True # their highway values must overlap. 


# ============================================================
# 2. Paths and layer names
# ============================================================

CITY_DIR = DATA_ROOT / CITY
PROCESSED_DIR = CITY_DIR / "processed"
OUTPUT_DIR = CITY_DIR / "outputs"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

J2J_GPKG = (
    PROCESSED_DIR
    / f"{CITY.lower()}_j2j_detailed_network.gpkg"
)

OUTPUT_GPKG = (
    PROCESSED_DIR
    / f"{CITY.lower()}_unified_street_network.gpkg"
)

MAPPING_CSV = (
    OUTPUT_DIR
    / f"{CITY.lower()}_level3a_to_level4_mapping.csv"
)

J2J_LAYER = "Level 3A: j2j_detailed_network"

OUTPUT_LAYER = "Level 4: unified_street_network"
DIAGNOSTIC_LAYER = "Level 4: parallel_pair_diagnostics"


# ============================================================
# 3. Helper functions
# ============================================================
# It is mainly used for comparing and aggregating fields like: name_values, highway_values
def normalize_values(value):
    """
    Convert scalar, list-like, or semicolon-separated values
    into a lowercase set of cleaned strings.
    """

    if value is None:
        return set()

    try:
        if pd.isna(value):
            return set()
    except (TypeError, ValueError):
        pass

    if isinstance(value, (list, tuple, set)):
        raw_values = value
    else:
        text = str(value).strip()

        text = (
            text
            .replace("[", "")
            .replace("]", "")
            .replace("'", "")
            .replace('"', "")
            .replace(";", ",")
        )

        raw_values = text.split(",")

    ignored = {
        "",
        "nan",
        "none",
        "null",
        "<na>",
    }

    return {
        str(v).strip().lower()
        for v in raw_values
        if str(v).strip().lower() not in ignored
    }

# This combines multiple values while removing duplicates. 
# This is used when two Level 3A carriageways become one Level 4 edge.
def unique_join(values):
    """
    Flatten and combine unique values using semicolons.
    """

    combined = set()

    for value in values:
        combined.update(normalize_values(value))

    return ";".join(sorted(combined))

# It is used when calculating weighted averages.
def safe_float(value):
    """
    Convert a value to float where possible.
    """

    try:
        result = float(value)

        if math.isfinite(result):
            return result

    except (TypeError, ValueError):
        pass

    return None

# This standardizes geometry before comparison.
def to_single_linestring(geometry):
    """
    Return one LineString suitable for comparison.

    If a MultiLineString remains after line merging, use its
    longest part.
    """

    if geometry is None or geometry.is_empty:
        return None

    if geometry.geom_type == "LineString":
        return geometry

    if geometry.geom_type == "MultiLineString":
        merged = linemerge(geometry)

        if merged.geom_type == "LineString":
            return merged

        if merged.geom_type == "MultiLineString":
            parts = [
                part
                for part in merged.geoms
                if not part.is_empty
            ]

            if not parts:
                return None

            return max(parts, key=lambda part: part.length)

    return None


def reverse_line(line):
    """
    Reverse the coordinate order of a LineString.
    """

    return LineString(list(line.coords)[::-1])

# this function checks whether reversing one line gives a better endpoint alignment.
# This makes both lines run in the same logical direction before comparison.
def orient_line_like_reference(reference, candidate):
    """
    Orient the candidate line in the same general direction
    as the reference line.

    The direction giving the lowest endpoint-to-endpoint
    distance is selected.
    """

    ref_start = reference.coords[0]
    ref_end = reference.coords[-1]

    candidate_start = candidate.coords[0]
    candidate_end = candidate.coords[-1]

    same_direction = (
        math.dist(ref_start, candidate_start)
        + math.dist(ref_end, candidate_end)
    )

    reverse_direction = (
        math.dist(ref_start, candidate_end)
        + math.dist(ref_end, candidate_start)
    )

    if reverse_direction < same_direction:
        return reverse_line(candidate)

    return candidate

# Normalized sampling makes comparison possible even if the two lines have slightly different lengths.
def sample_line(line, n_points):
    """
    Sample equally spaced normalized points along a line.
    """

    if line is None or line.is_empty or line.length == 0:
        return []

    if n_points < 2:
        n_points = 2

    return [
        line.interpolate(
            i / (n_points - 1),
            normalized=True,
        )
        for i in range(n_points)
    ]


def line_pair_metrics(line_a, line_b):
    """
    Compare two candidate carriageways.

    Returns:
    - length ratio;
    - mean corresponding-point separation;
    - maximum corresponding-point separation;
    - bidirectional close-overlap fraction.
    """

    line_a = to_single_linestring(line_a)
    line_b = to_single_linestring(line_b)

    if line_a is None or line_b is None:
        return None

    if line_a.length == 0 or line_b.length == 0:
        return None
# makes both run in the same direction.
    line_b = orient_line_like_reference(
        line_a,
        line_b,
    )
# 25 normalized points are created along both lines.
    points_a = sample_line(
        line_a,
        N_COMPARISON_POINTS,
    )

    points_b = sample_line(
        line_b,
        N_COMPARISON_POINTS,
    )

    corresponding_distances = [
        point_a.distance(point_b)
        for point_a, point_b in zip(
            points_a,
            points_b,
        )
    ]

    mean_separation = (
        sum(corresponding_distances)
        / len(corresponding_distances)
    )

    max_separation = max(corresponding_distances)
    # What proportion of each carriageway lies within 20 m of the other carriageway?
    # For every sampled point on A, checks the distance to the nearest location anywhere on B. Then do the same for every sampled point on B. The minimum of the two proportions is used as the overlap fraction.
    close_a_to_b = sum(
        point.distance(line_b)
        <= MAX_PARALLEL_DISTANCE_M
        for point in points_a
    ) / len(points_a)
    
    close_b_to_a = sum(
        point.distance(line_a)
        <= MAX_PARALLEL_DISTANCE_M
        for point in points_b
    ) / len(points_b)

    # It prevents a short line lying beside only part of a long line from appearing to have high overlap.
    overlap_fraction = min(
        close_a_to_b,
        close_b_to_a,
    )

    length_ratio = (
        min(line_a.length, line_b.length)
        / max(line_a.length, line_b.length)
    )
    # The average separation between the matched start endpoints and matched end endpoints. 
    # This is calculated and stored in diagnostics, but it is not currently used as a rejection threshold or in the pair score.
    endpoint_separation = (
        math.dist(
            line_a.coords[0],
            line_b.coords[0],
        )
        + math.dist(
            line_a.coords[-1],
            line_b.coords[-1],
        )
    ) / 2

    return {
        "length_ratio": length_ratio,
        "mean_separation_m": mean_separation,
        "max_separation_m": max_separation,
        "overlap_fraction": overlap_fraction,
        "endpoint_separation_m": endpoint_separation,
    }
# Checks whether the two edges share values for:
# name_values
# highway_values
def attribute_sets_compatible(
    row_a,
    row_b,
    column,
    require_match,
):
    """
    Check whether two aggregated Level 3A attributes are
    compatible.

    If one or both are missing, no pair is rejected.
    """

    if not require_match:
        return True

    if column not in row_a.index:
        return True

    values_a = normalize_values(row_a[column])
    values_b = normalize_values(row_b[column])

    if not values_a or not values_b:
        return True

    return bool(values_a.intersection(values_b))

# reject if:
# length ratio too low
# mean separation too high
# maximum separation too high
# overlap too low
# different known names
# different known highway types

# This is the actual accept/reject decision.
def evaluate_parallel_pair(
    row_a,
    row_b,
    connection_type,
):
    # gets all geometric measurements.
    metrics = line_pair_metrics(
        row_a.geometry,
        row_b.geometry,
    )

    if metrics is None:
        return {
            "is_candidate": False,
            "reject_reason": "invalid_geometry",
        }

    name_compatible = attribute_sets_compatible(
        row_a,
        row_b,
        "name_values",
        REQUIRE_NAME_MATCH_WHEN_AVAILABLE,
    )

    highway_compatible = attribute_sets_compatible(
        row_a,
        row_b,
        "highway_values",
        REQUIRE_HIGHWAY_OVERLAP_WHEN_AVAILABLE,
    )

    reasons = []

    minimum_length_ratio = (
        MIN_LENGTH_RATIO_J2D
        if connection_type == "J2D"
        else MIN_LENGTH_RATIO_J2J
    )

    if metrics["length_ratio"] < minimum_length_ratio:
        reasons.append("length_ratio")
    '''
    if (
        metrics["mean_separation_m"]
        > MAX_MEAN_SEPARATION_M
    ):
        reasons.append("mean_separation")
    
    if (
        metrics["max_separation_m"]
        > MAX_POINT_SEPARATION_M
    ):
    
        reasons.append("max_separation")
    '''
    minimum_overlap = (
        MIN_PARALLEL_OVERLAP_J2D
        if connection_type == "J2D"
        else MIN_PARALLEL_OVERLAP_J2J
    )

    if metrics["overlap_fraction"] < minimum_overlap:
        reasons.append("insufficient_overlap")

    if not name_compatible:
        reasons.append("different_names")

    if not highway_compatible:
        reasons.append("different_highway_types")
    # If there is no rejection reason, the pair becomes a valid candidate.
    is_candidate = len(reasons) == 0

    # Lower score means a better pairing.
    score = (
        metrics["mean_separation_m"]
        + metrics["max_separation_m"] * 0.25
        + (1 - metrics["length_ratio"]) * 20
        + (1 - metrics["overlap_fraction"]) * 20
    )

    return {
        **metrics,
        "name_compatible": name_compatible,
        "highway_compatible": highway_compatible,
        "is_candidate": is_candidate,
        "reject_reason": (
            ";".join(reasons)
            if reasons
            else ""
        ),
        "pair_score": score,
    }


def create_midpoint_centerline(
    geometry_a,
    geometry_b,
):
    """
    Create one centerline halfway between two carriageways.

    Both lines are sampled at equal normalized locations.
    The x/y midpoint of every corresponding sample pair is
    used to construct the new LineString.
    """

    line_a = to_single_linestring(geometry_a)
    line_b = to_single_linestring(geometry_b)

    if line_a is None or line_b is None:
        return None

    line_b = orient_line_like_reference(
        line_a,
        line_b,
    )
    # creates 50 sample points on each;
    points_a = sample_line(
        line_a,
        N_CENTERLINE_POINTS,
    )

    points_b = sample_line(
        line_b,
        N_CENTERLINE_POINTS,
    )

    coordinates = []

    for point_a, point_b in zip(
        points_a,
        points_b,
    ):
        # Calculate the midpoint between the two corresponding points.
        midpoint = (
            (point_a.x + point_b.x) / 2,
            (point_a.y + point_b.y) / 2,
        )

        if (
            not coordinates
            or midpoint != coordinates[-1]
        ):
            coordinates.append(midpoint)

    if len(coordinates) < 2:
        return None

    return LineString(coordinates)

# This decides which Level 3A edges are even allowed to be compared.
def canonical_connection_signature(row):
    """
    Create a grouping key for possible parallel carriageways.

    - Junction-to-junction edges are grouped by the same two junctions.
    - Junction-to-dead-end edges are grouped by their one junction only.
      Their dead-end node IDs are intentionally not used because the two
      parallel carriageways usually end at different dead-end nodes.
    """

    edge_type = row["edge_type"]

    start_id = row["start_junction_id"]
    end_id = row["end_junction_id"]

    if edge_type == "junction_to_junction":
        if pd.isna(start_id) or pd.isna(end_id):
            return None

        return (
            "J2J",
            *sorted(
                (
                    int(start_id),
                    int(end_id),
                )
            ),
        )

    if edge_type == "junction_to_dead_end":
        junction_id = (
            int(start_id)
            if not pd.isna(start_id)
            else int(end_id)
            if not pd.isna(end_id)
            else None
        )

        if junction_id is None:
            return None

        return (
            "J2D",
            junction_id,
        )

    return None

# Used when two carriageways are merged and you need to combine attributes. Longer carriageways contribute more heavily.
def length_weighted_numeric(
    group,
    column,
):
    """
    Calculate a length-weighted mean from source Level 3A
    edges.
    """

    if column not in group.columns:
        return None

    weighted_sum = 0.0
    valid_length = 0.0

    for _, row in group.iterrows():
        value = safe_float(row[column])
        length = safe_float(row["length_m"])

        if (
            value is None
            or length is None
            or length <= 0
        ):
            continue

        weighted_sum += value * length
        valid_length += length

    if valid_length == 0:
        return None

    return weighted_sum / valid_length


def aggregate_level4_row(
    level4_id,
    group,
    geometry,
    merge_status,
    pair_metrics=None,
):
    """
    Aggregate one or two Level 3A edges into one Level 4 row.
    """

    first = group.iloc[0]

    source_j2j_ids = unique_join(
        group["j2j_id"]
    )

    row = {
        "level4_id": level4_id,
        "merge_status": merge_status,
        "n_carriageways": len(group),
        "source_j2j_ids": source_j2j_ids,
        "edge_type": first.get(
            "edge_type",
            None,
        ),
        "start_junction_id": first.get(
            "start_junction_id",
            None,
        ),
        "end_junction_id": first.get(
            "end_junction_id",
            None,
        ),
        "n_source_edges": (
            pd.to_numeric(
                group.get(
                    "n_source_edges",
                    pd.Series(0, index=group.index),
                ),
                errors="coerce",
            )
            .fillna(0)
            .sum()
        ),
        "source_edge_ids": (
            unique_join(group["source_edge_ids"])
            if "source_edge_ids" in group.columns
            else None
        ),
        "length_m": geometry.length,
        "total_carriageway_length_m": (
            group.geometry.length.sum()
        ),
        "geometry": geometry,
    }

    if pair_metrics:
        row.update({
            "mean_carriageway_separation_m":
                pair_metrics["mean_separation_m"],
            "max_carriageway_separation_m":
                pair_metrics["max_separation_m"],
            "parallel_overlap_fraction":
                pair_metrics["overlap_fraction"],
            "carriageway_length_ratio":
                pair_metrics["length_ratio"],
        })
    else:
        row.update({
            "mean_carriageway_separation_m": None,
            "max_carriageway_separation_m": None,
            "parallel_overlap_fraction": None,
            "carriageway_length_ratio": None,
        })

    # Aggregate existing *_values fields.
    # Every field ending in: "_values" is treated as a set of values to be combined.
    for column in group.columns:
        if column.endswith("_values"):
            row[column] = unique_join(group[column])

    # Preserve important booleans.
    # if either carriageway has the feature, the Level 4 edge gets True.
    for column in [
        "has_sidewalk",
        "has_cycleway",
    ]:
        if column in group.columns:
            row[column] = bool(
                group[column]
                .fillna(False)
                .astype(bool)
                .any()
            )

    # Length-weighted fractions/representative values. aggregated by length:
    weighted_columns = [
        "sidewalk_length_fraction",
        "cycleway_length_fraction",
        "lit_length_fraction",
        "bridge_length_fraction",
        "tunnel_length_fraction",
        "parking_lane_length_fraction",
        "busway_length_fraction",
        "turn_lanes_length_fraction",
    ]

    for column in weighted_columns:
        if column in group.columns:
            row[column] = length_weighted_numeric(
                group,
                column,
            )

    # Width attributes.
    if "edge_width_weighted_mean" in group.columns:
        valid_widths = pd.to_numeric(
            group["edge_width_weighted_mean"],
            errors="coerce",
        )

        row["carriageway_width_mean_m"] = (
            valid_widths.mean()
        )

        row["carriageway_width_sum_m"] = (
            valid_widths.sum(
                min_count=1
            )
        )

    if "edge_width_min" in group.columns:
        row["edge_width_min"] = pd.to_numeric(
            group["edge_width_min"],
            errors="coerce",
        ).min()

    if "edge_width_max" in group.columns:
        row["edge_width_max"] = pd.to_numeric(
            group["edge_width_max"],
            errors="coerce",
        ).max()

    return row


# ============================================================
# 4. Load Level 3A network
# ============================================================

print("=" * 60)
print("Creating Level 4: Unified Street Network")
print("=" * 60)

print("Loading Level 3A J2J-Detailed network...")

j2j = gpd.read_file(
    J2J_GPKG,
    layer=J2J_LAYER,
)

required_columns = {
    "j2j_id",
    "edge_type",
    "start_junction_id",
    "end_junction_id",
    "geometry",
}

missing_columns = (
    required_columns
    - set(j2j.columns)
)

if missing_columns:
    raise KeyError(
        "The Level 3A layer is missing required columns: "
        f"{sorted(missing_columns)}"
    )

if j2j.crs is None:
    raise ValueError(
        "The Level 3A network has no CRS."
    )

if j2j.crs.is_geographic:
    raise ValueError(
        "The Level 3A network must use a projected CRS "
        "with metre-based coordinates."
    )

j2j = j2j.reset_index(drop=True)
j2j["_row_id"] = j2j.index

j2j["connection_signature"] = j2j.apply(
    canonical_connection_signature,
    axis=1,
)
print(f"Level 3A edges loaded: {len(j2j):,}")


# ============================================================
# 5. Generate candidate carriageway pairs
# ============================================================

print("Evaluating possible parallel carriageways...")

diagnostic_rows = []
candidate_rows = []

eligible = j2j[
    j2j["connection_signature"].notna()
].copy()
# puts edges into groups. 
for connection_signature, pair_group in eligible.groupby(
    "connection_signature"
):
    if len(pair_group) < 2:
        continue
    # Within each group tests every possible pair.
    for index_a, index_b in combinations(
        pair_group.index,
        2,
    ):
        row_a = j2j.loc[index_a]
        row_b = j2j.loc[index_b]

        result = evaluate_parallel_pair(
            row_a,
            row_b,
            connection_signature[0],
        )

        diagnostic_geometry = MultiLineString([
            to_single_linestring(row_a.geometry),
            to_single_linestring(row_b.geometry),
        ])

        if connection_signature[0] == "J2J":
            diagnostic_start_junction_id = connection_signature[1]
            diagnostic_end_junction_id = connection_signature[2]
        else:
            diagnostic_start_junction_id = connection_signature[1]
            diagnostic_end_junction_id = None

        diagnostic_row = {
            "j2j_id_a": int(row_a["j2j_id"]),
            "j2j_id_b": int(row_b["j2j_id"]),
            "connection_type": connection_signature[0],
            "start_junction_id": diagnostic_start_junction_id,
            "end_junction_id": diagnostic_end_junction_id,
            **result,
            "selected_pair": False,
            "geometry": diagnostic_geometry,
        }

        diagnostic_rows.append(diagnostic_row)

        if result["is_candidate"]:
            candidate_rows.append({
                "index_a": index_a,
                "index_b": index_b,
                "j2j_id_a": int(row_a["j2j_id"]),
                "j2j_id_b": int(row_b["j2j_id"]),
                **result,
            })

print(
    f"Geometrically valid candidate pairs: "
    f"{len(candidate_rows):,}"
)


# ============================================================
# 6. Select best one-to-one pairs
# ============================================================

# Sort best candidates first.
candidate_rows = sorted(
    candidate_rows,
    key=lambda row: row["pair_score"],
)

selected_pairs = []
# makes sure each Level 3A edge can belong to only one selected pair.
# If edge A already matched B, it cannot later also match C.
used_indices = set()

for candidate in candidate_rows:
    index_a = candidate["index_a"]
    index_b = candidate["index_b"]

    # One Level 3A edge may belong to only one pair.
    if (
        index_a in used_indices
        or index_b in used_indices
    ):
        continue

    selected_pairs.append(candidate)

    used_indices.add(index_a)
    used_indices.add(index_b)

selected_pair_ids = {
    frozenset((
        candidate["j2j_id_a"],
        candidate["j2j_id_b"],
    ))
    for candidate in selected_pairs
}

for diagnostic in diagnostic_rows:
    pair_id = frozenset((
        diagnostic["j2j_id_a"],
        diagnostic["j2j_id_b"],
    ))

    diagnostic["selected_pair"] = (
        pair_id in selected_pair_ids
    )

print(
    f"Selected parallel-carriageway pairs: "
    f"{len(selected_pairs):,}"
)


# ============================================================
# 7. Create Level 4 edges
# ============================================================

level4_rows = []
mapping_rows = []

level4_id = 1


# ------------------------------------------------------------
# A. Create one centerline per selected pair
# ------------------------------------------------------------

for pair in selected_pairs:
    index_a = pair["index_a"]
    index_b = pair["index_b"]

    pair_group = j2j.loc[
        [index_a, index_b]
    ].copy()

    centerline = create_midpoint_centerline(
        pair_group.iloc[0].geometry,
        pair_group.iloc[1].geometry,
    )

    if centerline is None or centerline.is_empty:
        # Do not lose the source edges if centerline creation fails.
        used_indices.discard(index_a)
        used_indices.discard(index_b)
        continue

    row = aggregate_level4_row(
        level4_id=level4_id,
        group=pair_group,
        geometry=centerline,
        merge_status="parallel_carriageways_merged",
        pair_metrics=pair,
    )

    level4_rows.append(row)

    for _, source_row in pair_group.iterrows():
        mapping_rows.append({
            "level4_id": level4_id,
            "source_j2j_id": int(
                source_row["j2j_id"]
            ),
            "merge_status":
                "parallel_carriageways_merged",
        })

    level4_id += 1


# ------------------------------------------------------------
# B. Keep every unmatched Level 3A edge unchanged
# ------------------------------------------------------------

for index, source_row in j2j.iterrows():
    if index in used_indices:
        continue

    source_group = j2j.loc[[index]].copy()

    geometry = to_single_linestring(
        source_row.geometry
    )

    if geometry is None or geometry.is_empty:
        continue

    row = aggregate_level4_row(
        level4_id=level4_id,
        group=source_group,
        geometry=geometry,
        merge_status="single_carriageway_or_unmatched",
        pair_metrics=None,
    )

    level4_rows.append(row)

    mapping_rows.append({
        "level4_id": level4_id,
        "source_j2j_id": int(
            source_row["j2j_id"]
        ),
        "merge_status":
            "single_carriageway_or_unmatched",
    })

    level4_id += 1


# ============================================================
# 8. Build outputs and coverage summary
# ============================================================

level4 = gpd.GeoDataFrame(
    level4_rows,
    geometry="geometry",
    crs=j2j.crs,
)

mapping = pd.DataFrame(mapping_rows)
# stores tested pairs.
diagnostics = gpd.GeoDataFrame(
    diagnostic_rows,
    geometry="geometry",
    crs=j2j.crs,
)

mapped_source_ids = set(
    mapping["source_j2j_id"]
) if not mapping.empty else set()

all_source_ids = set(
    j2j["j2j_id"].astype(int)
)

missing_source_ids = (
    all_source_ids
    - mapped_source_ids
)

print("=" * 60)
print("Level 4 quality summary")
print("=" * 60)
print(f"Input Level 3A edges: {len(j2j):,}")
print(f"Selected parallel pairs: {len(selected_pairs):,}")
print(f"Output Level 4 edges: {len(level4):,}")

n_merged_centerlines = (
    level4["merge_status"]
    == "parallel_carriageways_merged"
).sum()

n_unmatched_edges = (
    level4["merge_status"]
    == "single_carriageway_or_unmatched"
).sum()

print(f"Merged Level 4 centerlines: {n_merged_centerlines:,}")
print(f"Unmatched/single edges retained: {n_unmatched_edges:,}")
print(
    "Input Level 3A edges missing from mapping: "
    f"{len(missing_source_ids):,}"
)

if missing_source_ids:
    print("WARNING — missing source j2j_ids:")
    print(sorted(missing_source_ids))
# ------------------------------------------------------------
# Parallel carriageway summary
# ------------------------------------------------------------

n_parallel_j2j_edges = 2 * len(selected_pairs)

parallel_share = (
    n_parallel_j2j_edges / len(j2j)
    if len(j2j) > 0
    else 0
)

print("=" * 60)
print("Parallel carriageway summary")
print("=" * 60)
print(f"Total Level 3A edges: {len(j2j):,}")
print(f"Merged parallel carriageway pairs: {len(selected_pairs):,}")
print(f"Level 3A edges forming parallel carriageways: {n_parallel_j2j_edges:,}")
print(f"Share of Level 3A edges that are parallel carriageways: {parallel_share:.2%}")

# ============================================================
# 9. Save outputs
# ============================================================

if OUTPUT_GPKG.exists():
    print("Removing old output GeoPackage...")
    OUTPUT_GPKG.unlink()

print("Saving Level 4 network...")

level4.to_file(
    OUTPUT_GPKG,
    layer=OUTPUT_LAYER,
    driver="GPKG",
)

if not diagnostics.empty:
    diagnostics.to_file(
        OUTPUT_GPKG,
        layer=DIAGNOSTIC_LAYER,
        driver="GPKG",
    )

mapping.to_csv(
    MAPPING_CSV,
    index=False,
)

print("=" * 60)
print("Done.")
print("Saved GeoPackage:")
print(f"  {OUTPUT_GPKG}")
print("Layers:")
print(f"  - {OUTPUT_LAYER}")
print(f"  - {DIAGNOSTIC_LAYER}")
print("Saved mapping:")
print(f"  {MAPPING_CSV}")
print("=" * 60)