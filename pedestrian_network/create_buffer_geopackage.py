import geopandas as gpd
import os
import pandas as pd
from shapely.geometry import LineString
from shapely.affinity import translate

list_of_geopackage_filepath = []
list_of_filtered_geodataframes = []

def find_geopackages(mainfolder):
   
    for subfolder in os.listdir(mainfolder):
        subfolder_path = os.path.join(mainfolder, subfolder)
        if os.path.isdir(subfolder_path):
            for filename in os.listdir(subfolder_path):
                if filename.endswith('v1.3.gpkg'): # latest net version
                    filepath = os.path.join(subfolder_path, filename)
                    list_of_geopackage_filepath.append(filepath)
    print(len(list_of_geopackage_filepath))
    return list_of_geopackage_filepath


def filter_geopackages_by_non_empty_zahstelle(list_of_geopackage_filepath: str):
    for geopackage_filepath in list_of_geopackage_filepath:
        street_net_gdf = gpd.read_file(geopackage_filepath)
        street_net_gdf_filtered = street_net_gdf[street_net_gdf["Zaehlstelle"] != ""]
        list_of_filtered_geodataframes.append(street_net_gdf_filtered)
        print(street_net_gdf_filtered)
    return street_net_gdf_filtered

 

def concat_geopackages(list_of_filtered_geodataframes):
    return  pd.concat(list_of_filtered_geodataframes, ignore_index=True)
    

def buffer_left_right(line, buffer_distance=20):
    """
    Creates left and right buffers for a given LineString.

    Args:
        line (LineString): The input line geometry.
        buffer_distance (float): The buffer distance in meters.

    Returns:
        tuple: Two geometries (left_buffer, right_buffer)
    """
    # Offset the line to create left and right parallel lines
    left_line = line.parallel_offset(buffer_distance, side='left')
    right_line = line.parallel_offset(buffer_distance, side='right')

    # Create buffers around the left and right offset lines
    left_buffer = left_line.buffer(buffer_distance, cap_style=2)
    right_buffer = right_line.buffer(buffer_distance, cap_style=2)

    return left_buffer, right_buffer


def main():
    filepath = r"Z:\_Public\Projekte\IVST\058_FoPS_Fuss\02_Bearbeitung\QGIS_Data"
    
    filepath_zs = r"C:\Users\Goerner\Desktop\pedestrian_network\filtered_gdf_V2.gpkg"
    
    list_of_geopackage_filepath = find_geopackages(filepath) 
    
    list_of_filtered_geodataframes = filter_geopackages_by_non_empty_zahstelle(list_of_geopackage_filepath)
    print(len(list_of_filtered_geodataframes))
    filtered_geodataframe = concat_geopackages(list_of_filtered_geodataframes)
    filtered_geodataframe.to_file(" .gpkg", driver="GPKG")
    print(filtered_geodataframe)




if __name__ == "__main__":


    main()
    
    
