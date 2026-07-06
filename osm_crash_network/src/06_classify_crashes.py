from pathlib import Path
import re

import geopandas as gpd
import pandas as pd

# ============================================================
# 04_classify_and_aggregate_crashes.py
#
# Purpose:
# 1. Load crash shapefiles for multiple years
# 2. Keep only crashes for the city of interest
# 3. Classify crashes as intersection or segment crashes
# 4. Assign intersection crashes to junction_id
# 5. Assign segment crashes to nearest segment_id
# 6. Aggregate crash counts by type, mode, severity, year, etc.
# ============================================================

# -----------------------------
# User settings
# -----------------------------
CITY = "Dresden"

DATA_ROOT = Path(
    r"C:\Users\Golpayegani\GIS_Data\OSM_Crash_Network"
)

CRASH_DIR = DATA_ROOT / CITY / "crashes"

# Dresden municipality code in the Unfallatlas dataset.
# If this does not match your data, print UGEMEINDE value_counts first.
DRESDEN_UGEMEINDE = 6120000

MAX_SEGMENT_SNAP_DISTANCE_M = 30

# Fields to aggregate from the German crash database
AGGREGATE_COLUMNS = [
    "UKATEGORIE",
    "UART",
    "UTYP1",
    "ULICHTVERH",
    "IstRad",
    "IstPKW",
    "IstFuss",
    "IstKrad",
    "IstSonstig",
    "IstGkfz",
    "year",
    "UMONAT",
    "USTUNDE",
    "UWOCHENTAG",
    "mode_type",
    "severity_type",
    "light_type",
    "weekend",
]

# -----------------------------
# Input / output paths
# -----------------------------
CITY_DIR = DATA_ROOT / CITY
PROCESSED_DIR = CITY_DIR / "processed"
OUTPUT_DIR = CITY_DIR / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

JUNCTION_GPKG = PROCESSED_DIR / f"{CITY.lower()}_junction_areas_strict.gpkg"
SEGMENT_GPKG = PROCESSED_DIR / f"{CITY.lower()}_segment_network.gpkg"

OUTPUT_GPKG = OUTPUT_DIR / f"{CITY.lower()}_classified_and_aggregated_crashes.gpkg"

# -----------------------------
# Helper functions
# -----------------------------
def extract_year(path: Path):
    match = re.search(r"(20\d{2})", str(path))
    return int(match.group(1)) if match else None


def yes(value):
    return int(value) == 1 if pd.notna(value) else False


def derive_mode_type(row):
    car = yes(row.get("IstPKW", 0))
    bike = yes(row.get("IstRad", 0))
    ped = yes(row.get("IstFuss", 0))
    moto = yes(row.get("IstKrad", 0))
    heavy = yes(row.get("IstGkfz", 0))
    other = yes(row.get("IstSonstig", 0))

    if car and bike:
        return "car_bike"
    if car and ped:
        return "car_pedestrian"
    if car and moto:
        return "car_motorcycle"
    if car and heavy:
        return "car_heavy_vehicle"
    if bike and ped:
        return "bike_pedestrian"
    if bike and moto:
        return "bike_motorcycle"
    if heavy and ped:
        return "heavy_vehicle_pedestrian"
    if heavy and bike:
        return "heavy_vehicle_bike"
    if ped:
        return "pedestrian_involved"
    if bike:
        return "bike_involved"
    if moto:
        return "motorcycle_involved"
    if heavy:
        return "heavy_vehicle_involved"
    if car:
        return "car_involved"
    if other:
        return "other_involved"

    return "unknown"


def derive_severity_type(value):
    # German Unfallatlas commonly uses:
    # 1 = fatal
    # 2 = serious injury
    # 3 = slight injury
    if pd.isna(value):
        return "unknown"

    value = int(value)

    if value == 1:
        return "fatal"
    if value == 2:
        return "serious_injury"
    if value == 3:
        return "slight_injury"

    return f"severity_{value}"


def derive_light_type(value):
    # Common coding:
    # 0 = daylight
    # 1 = twilight
    # 2 = darkness
    if pd.isna(value):
        return "unknown"

    value = int(value)

    if value == 0:
        return "daylight"
    if value == 1:
        return "twilight"
    if value == 2:
        return "darkness"

    return f"light_{value}"


def clean_name(value):
    value = str(value)
    value = value.strip()
    value = value.replace(" ", "_")
    value = value.replace("-", "_")
    value = value.replace("/", "_")
    value = value.replace(".", "_")
    value = value.replace(":", "_")
    value = value.replace(";", "_")
    value = value.replace(",", "_")
    value = value.replace("(", "")
    value = value.replace(")", "")
    return value


def aggregate_counts(gdf, group_id_col, prefix):
    """
    Creates one wide table with:
    - total crashes
    - counts by selected crash attributes
    """

    outputs = []

    total = (
        gdf.groupby(group_id_col)
        .size()
        .reset_index(name=f"{prefix}_total_crashes")
    )
    outputs.append(total)

    for col in AGGREGATE_COLUMNS:
        if col not in gdf.columns:
            continue

        temp = (
            gdf.groupby([group_id_col, col])
            .size()
            .reset_index(name="count")
        )

        if temp.empty:
            continue

        wide = temp.pivot(
            index=group_id_col,
            columns=col,
            values="count"
        ).fillna(0)

        wide.columns = [
            f"{prefix}_{col}_{clean_name(c)}"
            for c in wide.columns
        ]

        wide = wide.reset_index()
        outputs.append(wide)

    merged = outputs[0]

    for table in outputs[1:]:
        merged = merged.merge(table, on=group_id_col, how="left")

    return merged.fillna(0)


# ============================================================
# Load crash data
# ============================================================
print("=" * 60)
print("Loading crash shapefiles")
print("=" * 60)

crash_files = sorted(CRASH_DIR.rglob("*.shp"))

if not crash_files:
    raise FileNotFoundError(f"No crash shapefiles found in:\n{CRASH_DIR}")

crash_layers = []

for file in crash_files:
    print(f"Reading: {file}")
    gdf = gpd.read_file(file)
    gdf["source_file"] = file.name

    file_year = extract_year(file)
    if "UJAHR" in gdf.columns:
        gdf["year"] = gdf["UJAHR"]
    else:
        gdf["year"] = file_year

    crash_layers.append(gdf)

crashes = pd.concat(crash_layers, ignore_index=True)
crashes = gpd.GeoDataFrame(
    crashes,
    geometry="geometry",
    crs=crash_layers[0].crs,
)

crashes = crashes.reset_index(drop=True)
crashes["crash_id"] = crashes.index + 1

print(f"Total crashes loaded: {len(crashes):,}")
print(f"Original CRS: {crashes.crs}")

# -----------------------------
# Keep only Dresden crashes
# -----------------------------
if "UGEMEINDE" in crashes.columns:
    print("Filtering crashes by UGEMEINDE...")
    print("Top municipality codes:")
    print(crashes["UGEMEINDE"].value_counts().head(10))

    before = len(crashes)

    crashes = crashes[
        crashes["UGEMEINDE"] == DRESDEN_UGEMEINDE
    ].copy()

    after = len(crashes)

    print(f"Crashes before city filter: {before:,}")
    print(f"Crashes after city filter: {after:,}")

    if after == 0:
        raise ValueError(
            "No crashes remain after filtering by UGEMEINDE. "
            "Check DRESDEN_UGEMEINDE."
        )
else:
    print(
        "WARNING: UGEMEINDE column not found. "
        "No administrative city filter applied."
    )

# -----------------------------
# Derived crash variables
# -----------------------------
print("Creating derived crash variables...")

crashes["mode_type"] = crashes.apply(derive_mode_type, axis=1)

if "UKATEGORIE" in crashes.columns:
    crashes["severity_type"] = crashes["UKATEGORIE"].apply(derive_severity_type)
else:
    crashes["severity_type"] = "unknown"

if "ULICHTVERH" in crashes.columns:
    crashes["light_type"] = crashes["ULICHTVERH"].apply(derive_light_type)
else:
    crashes["light_type"] = "unknown"

if "UWOCHENTAG" in crashes.columns:
    # Usually 1-7. We treat 6 and 7 as weekend.
    crashes["weekend"] = crashes["UWOCHENTAG"].apply(
        lambda x: "weekend" if pd.notna(x) and int(x) in [6, 7] else "weekday"
    )
else:
    crashes["weekend"] = "unknown"

# ============================================================
# Load network layers
# ============================================================
print("Loading junction and segment layers...")

junctions = gpd.read_file(JUNCTION_GPKG, layer="junction_areas")
segments = gpd.read_file(SEGMENT_GPKG, layer="segment_edges")

if crashes.crs is None:
    raise ValueError("Crash data has no CRS. Check the .prj files.")

if crashes.crs != junctions.crs:
    print("Reprojecting crashes to network CRS...")
    crashes = crashes.to_crs(junctions.crs)

if segments.crs != junctions.crs:
    segments = segments.to_crs(junctions.crs)

# ============================================================
# Classify crashes: intersection vs segment
# ============================================================
print("Classifying crashes as intersection or segment crashes...")

crashes_joined = gpd.sjoin(
    crashes,
    junctions[["junction_id", "geometry"]],
    how="left",
    predicate="intersects",
)

crashes_joined["crash_location_type"] = crashes_joined["junction_id"].apply(
    lambda x: "intersection" if pd.notna(x) else "segment"
)

intersection_crashes = crashes_joined[
    crashes_joined["crash_location_type"] == "intersection"
].copy()

segment_crashes = crashes_joined[
    crashes_joined["crash_location_type"] == "segment"
].copy()

print(f"Intersection crashes: {len(intersection_crashes):,}")
print(f"Segment crashes: {len(segment_crashes):,}")

# ============================================================
# Assign segment crashes to nearest segment
# ============================================================
print("Assigning segment crashes to nearest segment...")

segment_crashes_assigned = gpd.sjoin_nearest(
    segment_crashes,
    segments[["segment_id", "edge_id", "geometry"]],
    how="left",
    max_distance=MAX_SEGMENT_SNAP_DISTANCE_M,
    distance_col="distance_to_segment_m",
)

matched_segment_crashes = segment_crashes_assigned[
    segment_crashes_assigned["segment_id"].notna()
].copy()

unmatched_segment_crashes = segment_crashes_assigned[
    segment_crashes_assigned["segment_id"].isna()
].copy()

print(f"Matched segment crashes: {len(matched_segment_crashes):,}")
print(f"Unmatched segment crashes: {len(unmatched_segment_crashes):,}")

if len(segment_crashes) > 0:
    unmatched_share = len(unmatched_segment_crashes) / len(segment_crashes) * 100
    print(f"Unmatched segment crash share: {unmatched_share:.2f}%")

# ============================================================
# Aggregate crashes
# ============================================================
print("Aggregating intersection crashes by junction_id...")
junction_crash_counts = aggregate_counts(
    intersection_crashes,
    group_id_col="junction_id",
    prefix="junction",
)

junctions_with_crashes = junctions.merge(
    junction_crash_counts,
    on="junction_id",
    how="left",
).fillna(0)

print("Aggregating segment crashes by segment_id...")
segment_crash_counts = aggregate_counts(
    matched_segment_crashes,
    group_id_col="segment_id",
    prefix="segment",
)

segments_with_crashes = segments.merge(
    segment_crash_counts,
    on="segment_id",
    how="left",
).fillna(0)

# ============================================================
# Save outputs
# ============================================================
print("Saving outputs...")

crashes.to_file(
    OUTPUT_GPKG,
    layer="dresden_crashes_only",
    driver="GPKG",
)

crashes_joined.to_file(
    OUTPUT_GPKG,
    layer="all_classified_crashes",
    driver="GPKG",
)

intersection_crashes.to_file(
    OUTPUT_GPKG,
    layer="intersection_crashes",
    driver="GPKG",
)

matched_segment_crashes.to_file(
    OUTPUT_GPKG,
    layer="segment_crashes_assigned",
    driver="GPKG",
)

unmatched_segment_crashes.to_file(
    OUTPUT_GPKG,
    layer="segment_crashes_unmatched",
    driver="GPKG",
)

junctions_with_crashes.to_file(
    OUTPUT_GPKG,
    layer="junctions_with_crash_counts",
    driver="GPKG",
)

segments_with_crashes.to_file(
    OUTPUT_GPKG,
    layer="segments_with_crash_counts",
    driver="GPKG",
)

junction_crash_counts.to_csv(
    OUTPUT_DIR / f"{CITY.lower()}_junction_crash_counts.csv",
    index=False,
)

segment_crash_counts.to_csv(
    OUTPUT_DIR / f"{CITY.lower()}_segment_crash_counts.csv",
    index=False,
)

print("=" * 60)
print("Done.")
print(f"Saved GeoPackage:")
print(f"  {OUTPUT_GPKG}")
print("=" * 60)