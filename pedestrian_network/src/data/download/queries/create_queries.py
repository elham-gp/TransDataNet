from urllib.parse import quote

from utils.config_loader import config_data
from utils.load_data import area_key_value_dic, poi_key_value_dic

city = config_data["city_name"]
country_code = config_data["country_code"]
admin_level_city = config_data["admin_level_city"]
admin_level_country = config_data["admin_level_country"]
nameconvention = "name:en" if config_data["english_city_name"] else "name"

print("Fetch data for "+city+".")

def list_of_street_queries():
    """
    Generates a list of street queries based on combinations of cities and street types.

    Returns:
        list: A list of street queries for each combination of city and street type.
    """
    street_queries = []
    # Loop through combinations of cities and street types
    for street_type in config_data["street_types_list"]:
        query = f"""
        area["ISO3166-1"={country_code}][admin_level={admin_level_country}]->.country;
        area["{nameconvention}"="{city}"][admin_level={admin_level_city}]->.city;
        way[highway={street_type}](area.city)(area.country);
        (._;>;);
        out body;
        """
        street_queries.append(query)
    return street_queries

def list_of_poi_queries():
    """
    Generates a list of Point of Interest (POI) queries based on key-value pairs from a dictionary.

    Returns:
        list: A list of dictionaries containing the generated queries along with key and value information.
    """
    
    poi_queries = []
    '''
    for keys in poi_key_value_dic.keys():
        osm_key = quote(poi_key_value_dic[keys]["Key"])
        osm_value = quote(poi_key_value_dic[keys]["value"])
        # for testing

    '''

    for key, value in poi_key_value_dic.items():
        osm_key = quote(value["Key"])
        osm_value = quote(value["value"])

        
        # Use a list comprehension to generate queries for each value of the key
        '''
        queriy = f"""
            area["ISO3166-1"={country_code}][admin_level={admin_level_country}]->.country;
            area["{nameconvention}"="{city}"][admin_level={admin_level_city}]->.city;
            node[{osm_key}={osm_value}](area.city)(area.country);
            (._;>;);
            out body;
            """
        '''
        queriy = f"""
            area["ISO3166-1"={country_code}][admin_level={admin_level_country}]->.country;
            area["{nameconvention}"="{city}"][admin_level={admin_level_city}]->.city;
            node["{osm_key}"="{osm_value}"](area.city)(area.country);
            (._;>;);
            out body;
            """

        query_info = {"query":queriy,'key': osm_key, 'value': osm_value}    

        # Extend poi_queries with the generated queries
        poi_queries.append(query_info)


    return poi_queries

def list_of_area_queries():
    """
    Generates a list of area queries based on the keys and values in the area_key_value_dic dictionary.

    Returns:
        A list of dictionaries, each containing a query, key, and value.
    """  
    area_queries = []

    for keys in area_key_value_dic.keys():
        osm_key = quote(area_key_value_dic[keys]["Key"])  
        osm_value = quote(area_key_value_dic[keys]["value"])
        # Use a list comprehension to generate queries for each value of the key
        query = f"""
            area["ISO3166-1"={country_code}][admin_level={admin_level_country}]->.country;
            area["{nameconvention}"="{city}"][admin_level={admin_level_city}]->.city;
            (
            way[{osm_key}={osm_value}](area.city)(area.country);
            relation[{osm_key}={osm_value}](area.city)(area.country);
            );
            (._;>;);
            out geom;
            """
        
        query_info = {"query":query,'key': osm_key, 'value': osm_value}

        # Extend poi_queries with the generated queries
        area_queries.append(query_info)

    return area_queries

#creates lists of queres for overpass api
osm_street_queries = list_of_street_queries()
osm_poi_queries = list_of_poi_queries()
osm_area_queries = list_of_area_queries()
