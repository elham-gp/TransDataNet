import geopandas as gpd
from geopandas.tools import sjoin_nearest
from utils.config_loader import config_data
from utils.load_data import find_geo_packages
from utils.save_data import save_gdf_as_gpkg


# Read geometric packages
def read_geo_packages():
    """
    Reads and returns GeoDataFrames for street network and points of interest from the found geo packages.

    Returns:
        Dictionary with keys "street_net" and "pois" mapping to the respective GeoDataFrames.
    """
    geo_packages = find_geo_packages()
    return {
        "street_net": gpd.read_file(geo_packages["streets"]),
        "pois": gpd.read_file(geo_packages["pois"]),
    }

# Filter points of interest
def filter_pois(pois_gdf):
    """
    Filters points of interest GeoDataFrame into separate GeoDataFrames based on the type of public transportation.

    Args:
        pois_gdf: GeoDataFrame containing points of interest data.

    Returns:
        Tuple of three GeoDataFrames: pois_opnv_bus_gdf, pois_opnv_spnv_gdf, pois_opnv_strassenbahn_gdf.
    """
    pois_opnv_bus_gdf = pois_gdf[pois_gdf["Klasse"] == "Bushaltestelle"]
    pois_opnv_spnv_gdf = pois_gdf[pois_gdf["Klasse"] == "SPNV-Haltestelle"]
    pois_opnv_strassenbahn_gdf = pois_gdf[pois_gdf["Klasse"] == "Strassenbahnhaltestelle"]
    return pois_opnv_bus_gdf, pois_opnv_spnv_gdf, pois_opnv_strassenbahn_gdf

# Update street network with distances to points of interest
def assign_distance_opnv(street_net_optimized_updated_gdf, pois_opnv_bus_gdf, pois_opnv_spnv_gdf, pois_opnv_strassenbahn_gdf):
    """
    Assigns the distance from each street segment to the nearest public transportation points of interest.

    Args:
        street_net_optimized_updated_gdf: GeoDataFrame containing street network data.
        pois_opnv_bus_gdf: GeoDataFrame containing points of interest for bus stops.
        pois_opnv_spnv_gdf: GeoDataFrame containing points of interest for SPNV stops.
        pois_opnv_strassenbahn_gdf: GeoDataFrame containing points of interest for tram stops.

    Returns:
        None
    """
    if not pois_opnv_bus_gdf.empty:
        nearest_bus = sjoin_nearest(street_net_optimized_updated_gdf, pois_opnv_bus_gdf, distance_col="dist_bus", max_distance=2500)
        nearest_bus = nearest_bus.drop_duplicates(subset='geometry')

        street_net_optimized_updated_gdf['Entfernung Bushaltestelle'] = nearest_bus['dist_bus'].astype(int)

    if not pois_opnv_spnv_gdf.empty:
        nearest_spnv = sjoin_nearest(street_net_optimized_updated_gdf, pois_opnv_spnv_gdf, distance_col="dist_SPNV", max_distance=2500)
        nearest_spnv = nearest_spnv.drop_duplicates(subset='geometry')
        
        street_net_optimized_updated_gdf['Entfernung SPNV-Haltestelle'] = nearest_spnv['dist_SPNV'].astype(int)

    if not pois_opnv_strassenbahn_gdf.empty:
        nearest_strassenbahn = sjoin_nearest(street_net_optimized_updated_gdf, pois_opnv_strassenbahn_gdf, distance_col="dist_strassenbahn", max_distance=2500)
        nearest_strassenbahn = nearest_strassenbahn.drop_duplicates(subset='geometry')
        
        street_net_optimized_updated_gdf['Entfernung Strassenbahnhaltestelle'] = nearest_strassenbahn['dist_strassenbahn'].astype(int)
    save_gdf_as_gpkg(street_net_optimized_updated_gdf, f"street_net_" + config_data["city_name"], version = "1.8")
    
# Main function
def main():  # sourcery skip: remove-redundant-fstring
    geo_packages = read_geo_packages()
    print(geo_packages)
    street_net_optimized_updated_gdf = geo_packages["street_net"]
    pois_gdf = geo_packages["pois"]
    street_net_optimized_updated_gdf = street_net_optimized_updated_gdf.to_crs("EPSG:32188")
    pois_gdf = pois_gdf.to_crs("EPSG:32188")
    pois_opnv_bus_gdf, pois_opnv_spnv_gdf, pois_opnv_strassenbahn_gdf = filter_pois(pois_gdf)
    
    assign_distance_opnv(street_net_optimized_updated_gdf, pois_opnv_bus_gdf, pois_opnv_spnv_gdf, pois_opnv_strassenbahn_gdf)
    

if __name__ == "__main__":
    main()