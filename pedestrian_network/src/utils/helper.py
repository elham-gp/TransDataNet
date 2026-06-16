import os
import sys
from typing import List

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, Point

current_directory = os.getcwd()

sys.path.append('C:\\Users\\Hendr\\OneDrive\\Desktop\\pedestrian_network')
sys.path.append('C:\\Users\\Goerner\\Desktop\\pedestrian_network')

from utils.load_data import config_data


def start_end_points(line: LineString):
    
    start_point = Point(line.coords[0])
    end_point = Point(line.coords[-1])

    return start_point, end_point


def concatenate_geodataframes(gdf_list: List[gpd.GeoDataFrame]):
    #Concatenate a list of GeoDataFrames
    return pd.concat(gdf_list, ignore_index=True)

def overlay_geo_data(osm_gdf, optimized_gdf):
    return gpd.overlay(osm_gdf, optimized_gdf, how='intersection')


def file_exists(file_path):
    return os.path.exists(file_path)

def assign_to_dickey():
    list_of_dict_keys = [""]
    
def write_params_to_textfile(list_of_keys: list, params_file_name : str, purpose: str):
    # Log the correlation matrices to a text file
    output_file =params_file_name+'.txt'
    with open(output_file, 'w') as file:
        file.write(f"Purpose: {purpose}\n")
        file.write("\n")
        file.write("This textfile writes down the used parames for the above declared purpose and its used functions\n")
        file.write("\n")
       
        for key in list_of_keys:
            value = config_data[key]
            file.write(f"{key}: {value}""\n")
            
