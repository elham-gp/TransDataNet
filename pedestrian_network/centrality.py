from pathlib import Path
import re

import geopandas as gpd
import pandas as pd

from src.utils.config_loader import config_data


# ============================================================
# centrality.py
#
# Purpose:
# Semi-automatic sDNA centrality workflow.
#
# This script DOES NOT run sDNA itself.
#
# Workflow:
#
# MODE = "prepare"
#   1. Find latest existing street_net_<CITY>_v*.gpkg
#   2. Check the network
#   3. Add/preserve an sdna_id
#   4. Save a temporary analysis-ready copy in memory/output
#      only if needed for preserving the ID
#   5. Tell the user exactly which layer to use in QGIS
#
# Then manually in QGIS:
#   6. Run sDNA Integral
#   7. Save result as:
#      sdna_integral_<CITY>_v1.0.gpkg
#
# MODE = "process"
#   8. Load the sDNA result
#   9. Check fields and IDs
#   10. Save standardized:
#       sdna_centrality_<CITY>_v1.0.gpkg
#
# ============================================================


# ============================================================
# 1. User settings
# ============================================================

CITY = config_data["city_name"]

# Choose:
# "prepare"
# "process"
MODE = "prepare"


# ============================================================
# 2. Folder structure
# ============================================================

OUTPUT_ROOT = Path("src/data/output")

CITY_DIR = OUTPUT_ROOT / CITY
DRAFT_DIR = CITY_DIR / "draft"

DRAFT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# Manual QGIS/sDNA result
SDNA_RAW_OUTPUT = (
    DRAFT_DIR
    / f"sdna_integral_{CITY}_v1.0.gpkg"
)

# Standardized centrality output
SDNA_CENTRALITY_OUTPUT = (
    DRAFT_DIR
    / f"sdna_centrality_{CITY}_v1.0.gpkg"
)


# ============================================================
# 3. Helpers
# ============================================================

def version_tuple(path):
    """
    Extract version from filenames such as:

        street_net_Leipzig_v1.0.gpkg
        street_net_Leipzig_v1.2.gpkg
        street_net_Leipzig_v2.0.gpkg

    Returns:
        (major, minor)

    This is safer than sorting filenames alphabetically.
    """

    match = re.search(
        r"_v(\d+)\.(\d+)\.gpkg$",
        path.name,
        flags=re.IGNORECASE,
    )

    if not match:
        return (-1, -1)

    return (
        int(match.group(1)),
        int(match.group(2)),
    )


def find_latest_street_network():
    """
    Find the most recent versioned street network in:

        src/data/output/<CITY>/draft/
    """

    candidates = list(
        DRAFT_DIR.glob(
            f"street_net_{CITY}_v*.gpkg"
        )
    )

    if not candidates:
        raise FileNotFoundError(
            f"No street network found for {CITY} in:\n"
            f"{DRAFT_DIR}\n\n"
            "Expected something like:\n"
            f"street_net_{CITY}_v1.0.gpkg"
        )

    latest = max(
        candidates,
        key=version_tuple,
    )

    return latest


def check_street_network(streets):
    """
    Basic checks before using the layer in sDNA.
    """

    if streets.empty:
        raise ValueError(
            "Street network is empty."
        )

    if streets.crs is None:
        raise ValueError(
            "Street network has no CRS."
        )

    if streets.crs.is_geographic:
        raise ValueError(
            "Street network uses a geographic CRS.\n"
            "sDNA distance-based analysis should use a "
            "projected CRS in metres."
        )

    if "geometry" not in streets.columns:
        raise KeyError(
            "Street network has no geometry column."
        )

    invalid_geometry = (
        streets.geometry.isna()
        | streets.geometry.is_empty
    )

    if invalid_geometry.any():
        print(
            "WARNING: "
            f"{invalid_geometry.sum():,} "
            "street features have empty/missing geometry."
        )


def add_sdna_id(streets):
    """
    Add a stable ID for matching the sDNA result back to
    the source street segment.

    If sdna_id already exists, preserve it.
    """

    streets = streets.copy()

    if "sdna_id" not in streets.columns:

        streets = streets.reset_index(
            drop=True
        )

        streets["sdna_id"] = (
            streets.index + 1
        )

        print(
            "Added new 'sdna_id' field."
        )

    else:

        print(
            "Existing 'sdna_id' field found "
            "and preserved."
        )

    if streets["sdna_id"].duplicated().any():
        raise ValueError(
            "'sdna_id' is not unique."
        )

    return streets


# ============================================================
# 4. PREPARE MODE
# ============================================================

def prepare_for_sdna():

    street_path = (
        find_latest_street_network()
    )

    print("=" * 60)
    print("Preparing street network for sDNA")
    print("=" * 60)

    print(
        f"City: {CITY}"
    )

    print(
        "Latest street network:"
    )

    print(
        f"  {street_path}"
    )

    streets = gpd.read_file(
        street_path
    )

    check_street_network(
        streets
    )

    streets = add_sdna_id(
        streets
    )

    print(
        f"Street segments: "
        f"{len(streets):,}"
    )

    print(
        f"CRS: {streets.crs}"
    )

    # --------------------------------------------------------
    # IMPORTANT
    #
    # We need sdna_id to survive the QGIS/sDNA round trip.
    #
    # Therefore save an analysis copy only if the original
    # street network does not already contain sdna_id.
    # --------------------------------------------------------

    analysis_path = (
        DRAFT_DIR
        / f"street_net_{CITY}_sdna.gpkg"
    )

    streets.to_file(
        analysis_path,
        layer="street_net_sdna",
        driver="GPKG",
    )

    print("=" * 60)
    print("sDNA analysis input ready")
    print("=" * 60)

    print(
        "Open THIS file in QGIS:"
    )

    print(
        f"  {analysis_path}"
    )

    print()
    print(
        "Layer:"
    )
    print(
        "  street_net_sdna"
    )

    print()
    print(
        "Run:"
    )
    print(
        "  Processing Toolbox "
        "→ sDNA Integral"
    )

    print()
    print(
        "Make sure 'sdna_id' is preserved "
        "in the output."
    )

    print()
    print(
        "Save the sDNA output as:"
    )

    print(
        f"  {SDNA_RAW_OUTPUT}"
    )

    print()
    print(
        "Then change:"
    )

    print(
        '  MODE = "process"'
    )

    print(
        "and run centrality.py again."
    )


# ============================================================
# 5. PROCESS MODE
# ============================================================

def process_sdna_result():

    print("=" * 60)
    print("Processing sDNA centrality result")
    print("=" * 60)

    if not SDNA_RAW_OUTPUT.exists():
        raise FileNotFoundError(
            "The expected sDNA result does not exist:\n"
            f"{SDNA_RAW_OUTPUT}\n\n"
            "Run sDNA Integral in QGIS first."
        )

    sdna = gpd.read_file(
        SDNA_RAW_OUTPUT
    )

    if sdna.empty:
        raise ValueError(
            "The sDNA output is empty."
        )

    if "sdna_id" not in sdna.columns:
        raise KeyError(
            "The sDNA result does not contain 'sdna_id'.\n"
            "The source street ID must be preserved "
            "through the QGIS/sDNA analysis."
        )

    if sdna["sdna_id"].duplicated().any():
        raise ValueError(
            "Duplicate sdna_id values found "
            "in the sDNA result."
        )

    print(
        f"Features in sDNA result: "
        f"{len(sdna):,}"
    )

    print()
    print("=" * 60)
    print("Columns produced by sDNA")
    print("=" * 60)

    for column in sdna.columns:
        print(
            f"  {column}"
        )

    # --------------------------------------------------------
    # Save without renaming the sDNA fields yet.
    #
    # The exact field names depend on:
    # - sDNA version
    # - radius
    # - metric
    # - analysis settings
    #
    # After the first run we can identify the exact
    # closeness and betweenness columns.
    # --------------------------------------------------------

    sdna.to_file(
        SDNA_CENTRALITY_OUTPUT,
        layer="sdna_centrality",
        driver="GPKG",
    )

    print("=" * 60)
    print("Centrality processing complete")
    print("=" * 60)

    print(
        f"Saved:"
    )

    print(
        f"  {SDNA_CENTRALITY_OUTPUT}"
    )

    print()
    print(
        "Next step:"
    )

    print(
        "Inspect the printed sDNA fields and select "
        "the closeness and betweenness columns "
        "for pedestrian_volume.py."
    )


# ============================================================
# 6. Run
# ============================================================

if MODE == "prepare":

    prepare_for_sdna()

elif MODE == "process":

    process_sdna_result()

else:

    raise ValueError(
        "MODE must be either "
        "'prepare' or 'process'."
    )