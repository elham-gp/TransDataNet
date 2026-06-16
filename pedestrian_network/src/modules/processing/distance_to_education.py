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

    pois_kita_gdf = pois_gdf[pois_gdf["Klasse"] == "Kindergaerten"]
    pois_school_gdf = pois_gdf[pois_gdf["Klasse"] == "weiterfuehrende Schulen"]
    pois_university_gdf = pois_gdf[pois_gdf["Klasse"] == "Hochschulen"]
    return pois_kita_gdf, pois_school_gdf, pois_university_gdf

# Update street network with distances to points of interest
def assign_distance_education(street_net_optimized_updated_gdf, pois_kita_gdf, pois_school_gdf, pois_university_gdf):

    if not pois_kita_gdf.empty:
        nearest_bus = sjoin_nearest(street_net_optimized_updated_gdf, pois_kita_gdf, distance_col="dist_kita", max_distance=2500)
        nearest_bus = nearest_bus.drop_duplicates(subset='geometry')

        street_net_optimized_updated_gdf['Entfernung Kita'] = nearest_bus['dist_kita'].astype(int)

    if not pois_school_gdf.empty:
        nearest_spnv = sjoin_nearest(street_net_optimized_updated_gdf, pois_school_gdf, distance_col="dist_school", max_distance=2500)
        nearest_spnv = nearest_spnv.drop_duplicates(subset='geometry')
        
        street_net_optimized_updated_gdf['Entfernung weiterf Schule'] = nearest_spnv['dist_school'].astype(int)

    if not pois_university_gdf.empty:
        nearest_strassenbahn = sjoin_nearest(street_net_optimized_updated_gdf, pois_university_gdf, distance_col="dist_university", max_distance=2500)
        nearest_strassenbahn = nearest_strassenbahn.drop_duplicates(subset='geometry')
        
        street_net_optimized_updated_gdf['Entfernung Hochschule'] = nearest_strassenbahn['dist_university'].astype(int)

    save_gdf_as_gpkg(street_net_optimized_updated_gdf, f"street_net_" + config_data["city_name"], version = "1.7")
    
# Main function
def main():  # sourcery skip: remove-redundant-fstring
    geo_packages = read_geo_packages()
    street_net_optimized_updated_gdf = geo_packages["street_net"]
    pois_gdf = geo_packages["pois"]
    #only for canada
    street_net_optimized_updated_gdf = street_net_optimized_updated_gdf.to_crs("EPSG:32188")
    pois_gdf = pois_gdf.to_crs("EPSG:32188")
    
    pois_kita_gdf, pois_school_gdf, pois_university_gdf = filter_pois(pois_gdf)
    
    assign_distance_education(street_net_optimized_updated_gdf, pois_kita_gdf, pois_school_gdf, pois_university_gdf)
    

if __name__ == "__main__":
    main()