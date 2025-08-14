"""
"""

import geopandas as gpd
import overpy
from shapely.geometry import LineString
from tqdm import tqdm

from utils.config_loader import config_data
from utils.helper import concatenate_geodataframes
from utils.save_data import save_gdf_as_gpkg
from .queries.create_queries import osm_street_queries

# add near the other imports (top of file)
import os, time, overpy

# ---- unified helper (paste this, replacing the old one) ----
UA       = os.getenv("OX_USER_AGENT", "pedestrian_network (set OX_USER_AGENT)")
TIMEOUT  = int(os.getenv("OVERPASS_TIMEOUT", "240"))
RETRIES  = int(os.getenv("OVERPASS_RETRIES", "3"))

# overpy needs endpoints that end with /interpreter
MIRRORS = [
    os.getenv("OVERPASS_URL"),  # e.g. https://overpass.kumi.systems/api/interpreter
    "https://overpass.kumi.systems/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://overpass-api.de/api/interpreter",
]
MIRRORS = [m for m in MIRRORS if m]

def _query_overpass(*args):
    """
    Supports both call styles:
      _query_overpass(query)
      _query_overpass(api_overpass, query)
    """
    if len(args) == 1:
        query = args[0]
    elif len(args) >= 2:
        query = args[1]
    else:
        raise TypeError("_query_overpass needs a query string")

    last_err = None
    for url in MIRRORS:
        print(f"[overpass] trying {url}")
        api = overpy.Overpass(url=url, timeout=TIMEOUT, max_retry_count=0,
                              headers={"User-Agent": UA})
        for attempt in range(1, RETRIES + 1):
            try:
                return api.query(query)
            except (overpy.exception.OverpassTooManyRequests,
                    overpy.exception.OverpassGatewayTimeout) as e:
                last_err = e
                print(f"[overpass] {e.__class__.__name__} (attempt {attempt}/{RETRIES}) – backing off")
                time.sleep(5 * attempt)
            except Exception as e:
                last_err = e
                print(f"[overpass] error: {e} (attempt {attempt}/{RETRIES})")
                time.sleep(3 * attempt)
        print("[overpass] switching mirror…")
    raise last_err
# ---- end helper ----



api_overpass = overpy.Overpass()

'''
def _query_overpass(api, query):
    """
    Send a query to the Overpass API to retrieve geographic data.

    This function takes an API object and a query string, executing the query against the
    Overpass API. It is designed to facilitate the retrieval of OpenStreetMap data based
    on the provided query.

    Args:
        api: The Overpass API instance used to execute the query.
        query: A string representing the query to be sent to the Overpass API.

    Returns:
        The result of the API query.

    Raises:
        Exception: If there is an error during the query execution.
    """

    return api.query(query)
'''

def _parse_osm_result(result):
    """
    Parse the result from an Overpass API query to extract relevant OSM data.

    This function processes the result object returned by the Overpass API,
    extracting information about ways, 
    including their IDs, highway types, names, and geometries.
    The extracted data is structured into a dictionary 
    and returned as a GeoDataFrame for further analysis.

    Args:
        result: The result object from the Overpass API containing OSM data.

    Returns:
        A GeoDataFrame containing the parsed OSM data with columns for ID,
        highway type, name, and geometry.

    Raises:
        Exception: If the result does not contain valid data or if parsing fails.
    """

    data = {'id': [], 'highway': [], 'name': [], 'geometry': []}

    for way in result.ways:
        # if 'highway' in way.tags and way.tags['highway'] == 'primary':
        line = LineString([(node.lon, node.lat) for node in way.nodes])
        data['id'].append(way.id)
        data['highway'].append(way.tags.get('highway'))
        data['name'].append(way.tags.get('name'))
        data['geometry'].append(line)
        # Capture all tags for each way as a dictionary

    # create a GeoDataFrame from the dictionary
    return gpd.GeoDataFrame(data, crs="EPSG:4326").to_crs("EPSG:31468")  # type: ignore


def create_osm_streets_gdf():
    """
    Creates a GeoDataFrame of OpenStreetMap streets.

    This function queries the Overpass API with predefined street queries to retrieve
    OpenStreetMap street data. It then parses the result of the query and creates a
    GeoDataFrame of the streets. The resulting GeoDataFrame is saved as a GeoPackage file.

    Returns:
        GeoDataFrame: GeoDataFrame of OpenStreetMap streets.
    """

    # empty list to store the gdf
    list_of_gdf = []

    for street_query in tqdm(osm_street_queries, desc="Querying Overpass"):

        result = _query_overpass(api_overpass, street_query)
        gdf = _parse_osm_result(result)
        list_of_gdf.append(gdf)

    osm_streets_gdf = concatenate_geodataframes(list_of_gdf)

    save_gdf_as_gpkg(osm_streets_gdf, "osm_street_net_"+config_data["city_name"], interimresult=True, version="0.0")

    return osm_streets_gdf


def main():

    create_osm_streets_gdf()


if __name__ == "__main__":
    # for testing
    main()
