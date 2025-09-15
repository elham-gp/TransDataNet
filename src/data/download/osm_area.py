# add near the other imports (top of file)
import os, time, overpy

import logging

import geopandas as gpd
import overpy
from shapely.geometry import LineString, Polygon
from shapely.ops import polygonize
from tqdm import tqdm

from utils.config_loader import config_data
from utils.helper import concatenate_geodataframes
from utils.save_data import save_gdf_as_gpkg

from .osm_retry import fetch_osm_data
from .queries.create_queries import osm_area_queries
############################################New##################################################
import time
import random

OVERPASS_ENDPOINTS = [
    "https://lz4.overpass-api.de/api/interpreter",   # fast mirror
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
]

def overpass_query_with_retry(query, retries=7, base_sleep=2.0, timeout=300):
    """
    Tries multiple Overpass mirrors with exponential backoff.
    Handles 'Too many requests' and 'Server load too high' gracefully.
    """
    last_exc = None
    # start at a random mirror to spread load
    start = random.randrange(len(OVERPASS_ENDPOINTS))
    for i in range(retries):
        url = OVERPASS_ENDPOINTS[(start + i) % len(OVERPASS_ENDPOINTS)]
        api = overpy.Overpass(url=url, timeout=timeout)
        try:
            return overpass_query_with_retry(query)
        except (overpy.exception.OverpassTooManyRequests,
                overpy.exception.OverpassGatewayTimeout) as e:
            last_exc = e
            # backoff: 2, 4, 8, 16, 32, 64, 90s (capped)
            sleep_s = min(90.0, base_sleep * (2 ** i)) + random.random()
            time.sleep(sleep_s)
            continue
    raise last_exc if last_exc else RuntimeError("Overpass query failed without a specific exception")
#################################################################################################################

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

def _add_timeout_to_query(q: str) -> str:
    q = q.strip()
    # Add a global setting if the query doesn't already specify a timeout
    if "[timeout:" not in q:
        q = f"[timeout:{TIMEOUT}];" + q
    return q

def _query_overpass(*args):
    """
    Works with both call styles used in this repo:
      _query_overpass(query)
      _query_overpass(api_overpass, query)
    """
    if len(args) == 1:
        query = args[0]
    elif len(args) >= 2:
        query = args[1]
    else:
        raise TypeError("_query_overpass needs a query string")

    query = _add_timeout_to_query(query)
    last_err = None

    for url in MIRRORS:
        print(f"[overpass] trying {url}")
        # older overpy versions don't accept timeout/headers in ctor → don't pass them
        try:
            api = overpy.Overpass(url=url, max_retry_count=0)
        except TypeError:
            api = overpy.Overpass(url=url)

        for attempt in range(1, RETRIES + 1):
            try:
                return overpass_query_with_retry(query)
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

    # all mirrors failed
    raise last_err

# ---- end helper ----



# Configure logging
logging.basicConfig(filename='Result_area_insights.txt',
                    level=logging.INFO, filemode='w')

api = overpy.Overpass()
'''
def _query_overpass(query):
    """
    Query the Overpass API with the given query.

    Args:
        api: The Overpass API object.
        query: The query string to be executed with keys and values form osm.

    Returns:
        The result of the query.

    Raises:
        OverpassBadRequest: If the query is invalid.
    Examples:
        >>> api = OverpassAPI()
        >>> query = siehe queryservice
        >>> result = _query_overpass(api, query)
    """

    try:
        return fetch_osm_data(query)
        # Process the result as needed
    except Exception as e:
        print(f"Error fetching OSM data: {e}")  
'''

def _parse_osm_area_result(result: overpy.Result, osm_key: str, osm_value: str, **kwargs):
    """
    Parses the result of a query to a GeoDataFrame.

    Args:
        result: The result of the query.
    """

    # Create an empty dictionary to store the data
    data = {'id': [], 'osm_key': [], 'osm_value': [], 'geometry': []}
    result_polygons = []
    possible_double_ids = []
    inner_polygons = []

    for relation in result.relations:
        # Initialize lists to store outer and inner coordinates for each polygon
        outer_polygons = []
        

        for member in relation.members:
            member_ref = member.ref
            polygon_line_query = f"way({member_ref});(._;>;);out geom;"
            polygon_line_result = overpass_query_with_retry(polygon_line_query)
            for polygon_line in polygon_line_result.ways:
                    coordinates = [(node.lon, node.lat) for node in polygon_line.nodes]
                    line = LineString(coordinates)
                    polygons = list(polygonize([line]))
                    
                    for polygon in polygons:
                        if polygon.is_valid and polygon.area > 0:  # Check for validity and non-zero area

                            # Check if the member role is "inner" or "outer"
                            if member.role == "outer":
                                outer_polygons.append(polygon)
                                possible_double_ids.append(polygon_line.id)
                            elif member.role == "inner":
                                inner_polygons.append(polygon)
                                possible_double_ids.append(polygon_line.id)

        for outer_polygon in outer_polygons:
            # Create a copy of the outer polygon to avoid modifying the original
            current_polygon = outer_polygon

            # Subtract each inner polygon from the current outer polygon
            for inner_polygon in inner_polygons:
                current_polygon = current_polygon.difference(inner_polygon)

            # If the result is not empty, append it to the list
            if not current_polygon.is_empty:
                result_polygons.append((current_polygon, relation.id))
        
    for way in result.ways:
        # check if a way of the relation polygon is also a way from result
        if way.id in possible_double_ids:
            print(f" Doppelte id entdeckt in {osm_key} : {osm_value}")
        else:
            if len(way.nodes) >= 4:
                
                polygon = Polygon([(node.lon, node.lat) for node in way.nodes])
                if polygon.is_valid:
                    result_polygons.append((polygon, way.id))

    for polygon, polygon_id in result_polygons:
        data['id'].append(polygon_id)
        data['osm_key'].append(osm_key)
        data['osm_value'].append(osm_value)
        data['geometry'].append(polygon)

    # create a GeoDataFrame from the dictionary
    return gpd.GeoDataFrame(data, crs="EPSG:4326").to_crs("EPSG:31468") # type: ignore



def create_osm_area_gdf():
    """
    Creates a GeoDataFrame of OpenStreetMap areas.

    Returns: None
    """
    # empty list to store the gdf
    list_of_gdf = []

    for query_info in tqdm(osm_area_queries, desc="Querying Overpass"):
        area_query = query_info['query']

        osm_key = query_info['key']
        osm_value = query_info['value']
        result = _query_overpass(area_query)
        if result is not None:
            gdf = _parse_osm_area_result(result, osm_key, osm_value)
            list_of_gdf.append(gdf)
            # add information to logfile
            number_of_areas = len(result.areas)
            logging.info(
                f"{osm_key} OsmValue: {osm_value} Anzahl_areas {number_of_areas}")

        else:
            # Log the missing query to the log file
            logging.warning(f"Missing result for query: {osm_key} - {osm_value} in {number_of_areas}")

            continue
        
    if list_of_gdf is not None:

        osm_area_gdf = concatenate_geodataframes(list_of_gdf)
       
        save_gdf_as_gpkg(osm_area_gdf, "osm_area"+config_data["city_name"],  version="1.0")
        
        return osm_area_gdf
    else:
        logging.info("No area result in " + config_data["city_name"])

        return None

def main():

    create_osm_area_gdf()


if __name__ == "__main__":
    main()
