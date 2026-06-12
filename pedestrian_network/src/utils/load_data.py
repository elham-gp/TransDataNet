import os
import re
import pandas as pd

from .config_loader import config_data


def find_geo_packages(city_name=config_data["city_name"], output_folder="src/data/output"):
    """
    Find GeoPackage files in the specified draft! output folder that match the given city name and have the highest version.

    Args:
        city_name (str, optional): The name of the city to search for in the file names. Defaults to the value from config_data.
        output_folder (str, optional): The path to the output folder where the GeoPackage files are located. Defaults to "data/output".

    Returns:
        dict: A dictionary mapping the file keys to their corresponding file paths with the highest version number.
    """
    draft_folder = os.path.join(output_folder, city_name, "draft")
    if not os.path.exists(draft_folder):
        print(f"No draft folder found at {draft_folder}")
        return {}

    version_pattern = re.compile(r'_v(\d+(\.\d+)?(-\w+)?)')

    def extract_version(filename):
        match = version_pattern.search(filename)
        if match:
            return match.group(1)
        return None

    def compare_versions(v1, v2):
        v1_parts = v1.split('-')[0].split('.')
        v2_parts = v2.split('-')[0].split('.')
        for p1, p2 in zip(v1_parts, v2_parts):
            if int(p1) < int(p2):
                return -1
            elif int(p1) > int(p2):
                return 1
        if len(v1_parts) < len(v2_parts):
            return -1
        elif len(v1_parts) > len(v2_parts):
            return 1
        return 0

    gpkg_files = {}

    # Add fixed path for zensus file
    zensus_file_path = os.path.join(output_folder, "zensus_100x100.gpkg")
    print(zensus_file_path)
    if os.path.exists(zensus_file_path):
        gpkg_files["census"] = zensus_file_path
        print(zensus_file_path)
    for file in os.listdir(draft_folder):
        if file.endswith(".gpkg") and city_name in file:
            file_path = os.path.join(draft_folder, file)
            version = extract_version(file)
            if not version:
                continue  # Skip files without a valid version
            file_key = None
            
            if "street" in file:
                file_key = "streets"
            elif "area" in file:
                file_key = "areas"
            elif "pois" in file:
                file_key = "pois"
            elif "node" in file:
                file_key = "nodes"
            
            if file_key:
                if file_key not in gpkg_files:
                    gpkg_files[file_key] = (file_path, version)
                else:
                    current_version = gpkg_files[file_key][1]
                    if compare_versions(current_version, version) < 0:
                        gpkg_files[file_key] = (file_path, version)

    # Extract paths from the dictionary
    gpkg_files = {k: v[0] for k, v in gpkg_files.items()}
    print(gpkg_files)
    return gpkg_files

poi_csv = config_data["path_to_poi_csv"]
area_csv = config_data["path_to_area_csv"]
# Read the CSV file into a DataFrame

poi_key_value_df = pd.read_csv(poi_csv, sep=';')
area_key_value_df = pd.read_csv(area_csv, sep=';')

# Convert DataFrame to a dictionary
poi_key_value_dic = poi_key_value_df.to_dict('index')
# dictionary is wrong, better a diffferent attapt
area_key_value_dic = area_key_value_df.to_dict('index')
#TODO: create load function for the different used geodataframes
# like osm street net, osm_pois, 

