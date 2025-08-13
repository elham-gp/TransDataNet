from data.download.osm_area import create_osm_area_gdf
from modules.area_processing import assign_group_categorie_to_area

from utils.osm_config import configure
configure()



def main():
    """
    Executes the main functionality of the script by creating an OSM area GeoDataFrame and assigning group categories to the areas.

    """
    osm_area_gdf = create_osm_area_gdf()
    assign_group_categorie_to_area(osm_area_gdf) # type: ignore


if __name__ == "__main__":
    main()