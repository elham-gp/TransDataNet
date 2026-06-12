import geopandas as gpd
import pandas as pd

from utils.config_loader import config_data
from utils.load_data import poi_key_value_df
from utils.save_data import save_gdf_as_gpkg

def assign_group_categorie_poi(osm_poi_gdf: gpd.GeoDataFrame):
    """
    Merges the 'group' and 'categorie' columns of the osm_poi_gdf DataFrame with the poi_key_value_df DataFrame.
    The osm_poi_gdf DataFrame is updated and overwritten with the merged result.

    Args:
        osm_poi_gdf: The GeoDataFrame containing the OpenStreetMap points of interest data.

    Returns:
        The updated osm_poi_gdf DataFrame with the 'group' and 'categorie' columns merged.

    """
    # merge group and categorie
    # updates and overwrites the osm_poi_gdf
    osm_poi_gdf = pd.merge(osm_poi_gdf, poi_key_value_df, left_on=[
                           'osm_key', 'osm_value'], right_on=['Key', 'value'], how='left') # type: ignore   
    save_gdf_as_gpkg(osm_poi_gdf, "osm_pois_"+config_data["city_name"], version="1.1")  

    return osm_poi_gdf

