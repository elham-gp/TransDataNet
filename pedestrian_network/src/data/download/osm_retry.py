import time

import overpy


def fetch_osm_data(query, retries=5, delay=10):
    """
    Fetch OSM data using Overpass API with retry mechanism.

    Parameters:
        query (str): The Overpass API query.
        retries (int): Number of retries if a timeout occurs. Default is 5.
        delay (int): Delay in seconds between retries. Default is 10 seconds.

    Returns:
        overpy.Result: The result from the Overpass API query.
    """
    api = overpy.Overpass()
    attempt = 0

    while attempt < retries:
        try:
            return api.query(query)
        except overpy.exception.OverpassGatewayTimeout:
            attempt += 1
            print(f"Overpass API timeout. Retrying {attempt}/{retries} in {delay} seconds...")
            time.sleep(delay)

    raise ValueError("Failed to fetch OSM data after multiple retries due to Overpass API timeout.")
