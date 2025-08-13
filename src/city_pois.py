
from data.download.osm_pois import create_osm_poi_gdf
from modules.poi_processing import assign_group_categorie_poi

#from utils.osm_config import configure
#configure()


def main():

    osm_poi_gdf = create_osm_poi_gdf()
    assign_group_categorie_poi(osm_poi_gdf) # type: ignore

if __name__ == "__main__":
    main()
