from data.download.osm_streets import create_osm_streets_gdf
from modules.street_net_creation import create_street_net_and_intersection_gpkg

#from utils.osm_config import configure
#configure()


def main():
    
    osm_street_net = create_osm_streets_gdf()
    create_street_net_and_intersection_gpkg(osm_street_net) # type: ignore
    
if __name__ == "__main__":
    main()
