# ============================================================
# pedestrian_volume.py
#
# Purpose:
# Calculate pedestrian volume for an already processed city
# without rerunning pedestrian_network/main.py.
#
# Inputs:
# - existing city street network
# - sDNA centrality result
#
# Current NB model:
# - service/retail/gastronomy per length
# - hotels/pensions per length
#
# A closeness term can be activated later after the NB model
# has been refitted and a valid coefficient is available.
# ============================================================

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from src.utils.config_loader import config_data
from src.utils.load_data import find_geo_packages


# ============================================================
# User settings
# ============================================================

CITY = config_data["city_name"]

OUTPUT_ROOT = Path("src/data/output")
CITY_OUTPUT_DIR = OUTPUT_ROOT / CITY
DRAFT_DIR = CITY_OUTPUT_DIR / "draft"

DRAFT_DIR.mkdir(parents=True, exist_ok=True)


CENTRALITY_GPKG = (
    DRAFT_DIR
    / f"sdna_centrality_{CITY}_v1.0.gpkg"
)

OUTPUT_GPKG = (
    DRAFT_DIR
    / f"pedestrian_volume_{CITY}_v1.0.gpkg"
)


# ------------------------------------------------------------
# Existing NB model variables
# ------------------------------------------------------------

SERVICE_COL = (
    "Dienstleistung, Einzelhandel, Gastronomie: Anzahl"
)

HOTEL_COL = (
    "Hotels, Pensionen: Anzahl"
)


# ------------------------------------------------------------
# sDNA field names
#
# IMPORTANT:
# Replace these after your first sDNA Integral run with the
# actual column names produced by your chosen radius/settings.
# ------------------------------------------------------------

CLOSENESS_COL = None
BETWEENNESS_COL = None


# ------------------------------------------------------------
# Existing model coefficients
# ------------------------------------------------------------

B0 = 6.923
B1 = 0.006
B2 = 0.098


# ------------------------------------------------------------
# Optional future closeness coefficient
#
# Keep None until you refit the NB model with closeness.
# ------------------------------------------------------------

B_CLOSENESS = None


# ============================================================
# Load existing street network
# ============================================================

def load_street_network():

    geo_packages = find_geo_packages(
        city_name=CITY,
        output_folder=str(OUTPUT_ROOT),
    )

    if "streets" not in geo_packages:
        raise FileNotFoundError(
            f"No existing street network found for {CITY}."
        )

    street_path = geo_packages["streets"]

    print(f"Loading street network:")
    print(f"  {street_path}")

    streets = gpd.read_file(
        street_path
    ).reset_index(drop=True)

    # Must reproduce the same rows used for sDNA preparation.
    streets["sdna_id"] = streets.index + 1

    return streets


# ============================================================
# Add sDNA variables
# ============================================================

def add_centrality_variables(streets):

    if not CENTRALITY_GPKG.exists():

        print(
            "No sDNA centrality file found. "
            "PV will be calculated without centrality."
        )

        return streets

    print("Loading sDNA centrality...")

    centrality = gpd.read_file(
        CENTRALITY_GPKG,
        layer="sdna_centrality",
    )

    if "sdna_id" not in centrality.columns:
        raise KeyError(
            "Centrality layer has no 'sdna_id' field."
        )

    columns_to_keep = [
        "sdna_id",
    ]

    if CLOSENESS_COL is not None:

        if CLOSENESS_COL not in centrality.columns:
            raise KeyError(
                f"Closeness field not found: "
                f"{CLOSENESS_COL}"
            )

        columns_to_keep.append(
            CLOSENESS_COL
        )

    if BETWEENNESS_COL is not None:

        if BETWEENNESS_COL not in centrality.columns:
            raise KeyError(
                f"Betweenness field not found: "
                f"{BETWEENNESS_COL}"
            )

        columns_to_keep.append(
            BETWEENNESS_COL
        )

    centrality_data = centrality[
        columns_to_keep
    ].copy()

    streets = streets.merge(
        centrality_data,
        on="sdna_id",
        how="left",
    )

    return streets


# ============================================================
# Check model variables
# ============================================================

def check_required_variables(streets):

    required = [
        "laenge [km]",
        SERVICE_COL,
        HOTEL_COL,
    ]

    missing = [
        column
        for column in required
        if column not in streets.columns
    ]

    if missing:
        raise KeyError(
            "The existing street network is missing "
            "required PV variables:\n"
            f"{missing}\n\n"
            "These variables must already have been created "
            "by the city data-processing workflow."
        )


# ============================================================
# Calculate explanatory variables
# ============================================================

MODEL_VARIABLES = {
    "service": {
        "source_col": "Dienstleistung, Einzelhandel, Gastronomie: Anzahl",
        "transform": "per_length",
        "coefficient": 0.006,
    },

    "hotels": {
        "source_col": "Hotels, Pensionen: Anzahl",
        "transform": "per_length",
        "coefficient": 0.098,
    },

    "closeness": {
        "source_col": "Closeness_800",
        "transform": "none",
        "coefficient": 0.250,
    },
}

def calculate_model_variables(streets):

    denominator = (
        pd.to_numeric(
            streets["laenge [km]"],
            errors="coerce",
        )
        * 10.0
    ).replace(0, np.nan)

    for variable_name, settings in MODEL_VARIABLES.items():

        source_col = settings["source_col"]
        transform = settings["transform"]

        if source_col not in streets.columns:
            raise KeyError(
                f"Required model variable not found: {source_col}"
            )

        values = pd.to_numeric(
            streets[source_col],
            errors="coerce",
        )

        if transform == "per_length":
            values = values.fillna(0) / denominator

        elif transform == "none":
            pass

        else:
            raise ValueError(
                f"Unknown transformation: {transform}"
            )

        streets[f"PV_x_{variable_name}"] = values

    return streets
# ============================================================
# Apply Negative Binomial mean model
# ============================================================

def calculate_pedestrian_volume(streets):

    linear_predictor = B0

    for variable_name, settings in MODEL_VARIABLES.items():

        coefficient = settings["coefficient"]

        linear_predictor = (
            linear_predictor
            + coefficient
            * streets[f"PV_x_{variable_name}"]
        )

    streets["PV"] = (
        np.exp(linear_predictor)
        .fillna(0)
        .round(0)
    )

    return streets


# ============================================================
# Main standalone workflow
# ============================================================

def main():

    print("=" * 60)
    print("Pedestrian Volume modelling")
    print(f"City: {CITY}")
    print("=" * 60)

    streets = load_street_network()

    check_required_variables(
        streets
    )

    streets = add_centrality_variables(
        streets
    )

    streets = calculate_model_variables(
        streets
    )

    streets = calculate_pedestrian_volume(
        streets
    )

    streets.to_file(
        OUTPUT_GPKG,
        layer="pedestrian_volume",
        driver="GPKG",
    )

    print("=" * 60)
    print("Done.")
    print(f"Street segments: {len(streets):,}")
    print(f"Saved:")
    print(f"  {OUTPUT_GPKG}")
    print("=" * 60)


if __name__ == "__main__":
    main()