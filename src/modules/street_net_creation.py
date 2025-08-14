import geopandas as gpd
from shapely.ops import linemerge
from utils.config_loader import config_data
from utils.helper import start_end_points
from utils.save_data import save_gdf_as_gpkg


def optimize_street_network(gdf_osm_net: gpd.GeoDataFrame):
    """combines the linestring elements in a geodataframe to one entity

    Args:
        gdf_osm_net (geodataframe): represents a network of a city 

    Returns:
        geodataframe: geodataframe that contains one linestring element
    """

    # Use unary_union to merge the LineStrings into a single MultiLineString
    merged_multilinestring = gdf_osm_net["geometry"].unary_union
    # Merge every LineString that can be merged
    merged_linestring = linemerge(merged_multilinestring)

    street_net_gdf = gpd.GeoDataFrame(
        geometry=[merged_linestring], crs=gdf_osm_net.crs) # type: ignore
    gdf_street_net_optimized = street_net_gdf.explode(index_parts=False)
    gdf_street_net_optimized.reset_index(inplace=True, drop=True)
    return assign_values_to_new_street_net(gdf_osm_net, gdf_street_net_optimized)  # type: ignore
    
    

def assign_values_to_new_street_net(gdf_osm_net: gpd.GeoDataFrame, gdf_street_net_optimized: gpd.GeoDataFrame):
    """
    Assign values from an OpenStreetMap network to an optimized street network GeoDataFrame.

    This function iterates through the optimized street network and assigns attributes from the OpenStreetMap network based on geometric intersections. It ensures that the optimized street network is enriched with relevant data, such as highway type and name, by finding the longest intersecting lines.

    Args:
        gdf_osm_net (gpd.GeoDataFrame): The GeoDataFrame containing the original OpenStreetMap street network.
        gdf_street_net_optimized (gpd.GeoDataFrame): The GeoDataFrame representing the optimized street network to which values will be assigned.

    Returns:
        gpd.GeoDataFrame: The updated optimized street network GeoDataFrame with assigned values from the OpenStreetMap network.
    """
        
    # Iteriere über die kürzeren Linestrings und finde die entsprechenden Werte in df1
    
    
    for index, row in gdf_street_net_optimized.iterrows():
        # Find the lines that intersect
        intersecting_rows = gdf_osm_net[gdf_osm_net.intersects(row['geometry'])]

        if not intersecting_rows.empty:
            # Calculate intersection lengths
            intersecting_rows['intersection_length'] = intersecting_rows.apply(lambda x: row['geometry'].intersection(x['geometry']).length, axis=1)
            
            # Find the row with the maximum intersection length
            longest_intersecting_row = intersecting_rows.loc[intersecting_rows['intersection_length'].idxmax()]
            
            # Set the values in gdf_street_net_optimized
            gdf_street_net_optimized.at[index, 'highway'] = longest_intersecting_row['highway']
            gdf_street_net_optimized.at[index, 'name'] = longest_intersecting_row['name']
            
            
    return gdf_street_net_optimized


def create_support_points(gdf):
    """
    Generate support points from the geometries in a GeoDataFrame.

    This function extracts the first and last points from each line geometry in the provided GeoDataFrame, 
    creating a new GeoDataFrame that contains these support points. The resulting GeoDataFrame is reset and 
    exploded to handle any multipoint geometries.

    Args:
        gdf: A GeoDataFrame containing line geometries from which support points will be extracted.

    Returns:
        A GeoDataFrame containing the support points with the same coordinate reference system as the input.

    Raises:
        Exception: If the input GeoDataFrame does not contain valid geometries.
    """

    # extract support points as first and last point of an line
    result_list = gdf['geometry'].apply(start_end_points).to_list()

    # listcomprehension from tuple of points
    points_list = [
        point for tuple_points in result_list for point in tuple_points]

    # Create a new GeoDataFrame from the result list
    support_points_gdf = gpd.GeoDataFrame(geometry=points_list, crs=gdf.crs) # type: ignore

    # Reset the index abd explode possible multipoints
    return support_points_gdf.reset_index(drop=True).explode(index_parts=False) # type: ignore


def buffer_points(support_points_gdf):
    """
    Create buffered geometries around support points in a GeoDataFrame.

    This function takes a GeoDataFrame of support points, explodes any multipoint geometries, and generates 
    a new GeoDataFrame containing buffered geometries around each support point. The buffer distance is set to 
    0.5 units, allowing for spatial analysis of the surrounding area.

    Args:
        support_points_gdf: A GeoDataFrame containing support points to be buffered.

    Returns:
        A GeoDataFrame containing the buffered geometries of the support points.

    Raises:
        Exception: If the input GeoDataFrame does not contain valid geometries or if the buffering process fails.
    """

    support_points_gdf = support_points_gdf.explode(index_parts=False)

    buffered_points_gdf = gpd.GeoDataFrame(
        geometry=support_points_gdf['geometry'].buffer(0.5), crs=support_points_gdf.crs) # type: ignore
    buffered_points_gdf.reset_index(drop=True, inplace=True)

    return buffered_points_gdf


def find_intersecting_lines(gdf_lines, gdf_buffers, gdf_support_points):
    """
    Finds the points that represents intersections 

    Args:
        gdf_lines: A GeoDataFrame representing the lines.
        gdf_buffers: A GeoDataFrame representing the buffered support points.
        gdf_support_points: A GeoDataFrame representing the support points.

    Returns:
        A GeoDataFrame containing the support points that intersect with at least 3 lines.
    """

    # Create spatial index for buffered support points
    # NOTE:like a boundingbox around the point
    spatial_index = gdf_buffers.sindex

    # creat column with number of lines that intersect with the buffered support points
    gdf_buffers['Number_of_intersections'] = 0
    gdf_support_points['Number_of_intersections'] = 0

    # Iterate through each line and use spatial index for intersection check
    for line_id, line in gdf_lines.iterrows():
        possible_matches_index = list(
            spatial_index.intersection(line.geometry.bounds))
        possible_matches = gdf_buffers.iloc[possible_matches_index]

        for buffer_id, buffer_point in possible_matches.iterrows():
            if line.geometry.intersects(buffer_point.geometry):
                gdf_buffers.at[buffer_id, 'Number_of_intersections'] += 1
                gdf_support_points.at[buffer_id,
                                      'Number_of_intersections'] += 1
                # print(buffer_id,gdf_buffers.at[buffer_id, 'Number_of_intersections'])

    return gdf_support_points[gdf_support_points["Number_of_intersections"] >= 3]


def create_street_net_and_intersection_gpkg(osm_street_net: gpd.GeoDataFrame):
    """
    Create a street network and intersection GeoPackage.

    Args:
        osm_street_net: GeoDataFrame containing the downloaded OSM street network.

    Returns:
        None

    This function combines the downloaded OSM street network, optimizes it by merging 
    the LineString elements into one entity, and calculates the length for each LineString.
    It then creates a GeoDataFrame with support points, buffers the support points, and counts the number of intersecting lines in the buffered points.
    The resulting GeoDataFrames are saved as a GeoPackage file.
    """
    # combine downloaded osm net
    gdf_street_net_optimized = optimize_street_network(osm_street_net)

    # Calculate the length for each LineString and create a new column 'length'
    gdf_street_net_optimized['laenge [km]'] = gdf_street_net_optimized['geometry'].apply(
        lambda x: x.length)
    
    #gdf_street_net_optimized['laenge [km]'] = round(gdf_street_net_optimized['laenge [km]'] / 1000, 3)
    gdf_street_net_optimized['laenge [km]'] = round(gdf_street_net_optimized.geometry.length / 1000, 3)

    # create gdf with support points
    gdf_support_points = create_support_points(gdf_street_net_optimized)

    # buffer support points
    gdf_bufferd_points = buffer_points(gdf_support_points)
    # count intersecting lines in buffered points and write to support point with same ID
    gdf_intersections_points = find_intersecting_lines(
        gdf_street_net_optimized, gdf_bufferd_points, gdf_support_points)
    
    save_gdf_as_gpkg(gdf_street_net_optimized, "street_net_"+config_data["city_name"], version="1.0")
    save_gdf_as_gpkg(gdf_intersections_points, "node_points_"+config_data["city_name"], version="1.0")
    save_gdf_as_gpkg(osm_street_net, "osm_street_net_"+config_data["city_name"],interimresult= True) 
    save_gdf_as_gpkg(gdf_support_points, "support_points_"+config_data["city_name"],interimresult= True) 
    save_gdf_as_gpkg(gdf_bufferd_points, "buffer_points_"+config_data["city_name"], interimresult= True)
    return gdf_street_net_optimized, gdf_intersections_points



def main():
    
    print("test")
    # osm_street_net = create_osm_streets_gdf()

    # gdf_street_net_optimized, gdf_intersections_points = create_street_net_and_intersection_gpkg(osm_street_net)
    # #save_gdf_as_gpkg((gdf_street_net_optimized, "street_net_optimized_"+config_data["city_name"]), (gdf_intersections_points, "node_points_"+config_data["city_name"]))
    
if __name__ == "__main__":
    main()
