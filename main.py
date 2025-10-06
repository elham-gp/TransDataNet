import geopandas as gpd
import pandas as pd
from tqdm import tqdm
import os

from src.utils.config_loader import config_data
from src.utils.load_data import find_geo_packages
from src.utils.save_data import save_gdf_as_gpkg

from shapely.geometry import box

#buffer in meter
buffersize = config_data["street_buffer_size"]
'''
# if population improvement applies:
# make square buffers around census points 
SQUARE_HALF_SIDE_M = 50  # 50 m → 100 m squares; adjust as needed
'''
#counts_csv_filepath = r""

# census = r"src\data\output\zensus_100x100.gpkg"

# census_data = pd.read_csv(census, encoding='latin-1',sep=",")

geo_packages = find_geo_packages()
# filepaths to files using
street_net_optimized_filepath = geo_packages["streets"]
area_filepath = geo_packages["areas"]
pois_filepath = geo_packages["pois"]

# Check if file exists and is not empty
if not os.path.exists(pois_filepath) or os.path.getsize(pois_filepath) == 0:
    raise ValueError(f"GeoPackage file '{pois_filepath}' is missing or empty.")
#print(f"POI GeoPackage File Path: {pois_filepath}")
layers = gpd.read_file(pois_filepath, layer=None)
print("Available Layers:", layers)
print("File Size:", os.path.getsize(pois_filepath))

nodes_filepath = geo_packages["nodes"]
census_filepath = r"src\data\output\zensus_100x100.gpkg"

# read geopackages
street_net_optimized_gdf = gpd.read_file(street_net_optimized_filepath)
area_gdf = gpd.read_file(area_filepath)
pois_gdf = gpd.read_file(pois_filepath)
census_gdf = gpd.read_file(census_filepath)

'''
# if population improvement applies:
census_pts = census_gdf.to_crs(street_net_optimized_buffered_gdf.crs).copy()

def square_from_point(p, h):
    return box(p.x - h, p.y - h, p.x + h, p.y + h)

census_sq = census_pts.copy()
census_sq["geometry"] = census_pts.geometry.apply(lambda p: square_from_point(p, SQUARE_HALF_SIDE_M))
census_sq["Einwohner"] = pd.to_numeric(census_sq["Einwohner"], errors="coerce").fillna(0.0)

census_sq_sindex = census_sq.sindex
'''

#area_gdf = area_gdf.to_crs("EPSG:32188")
#pois_gdf = pois_gdf.to_crs("EPSG:32188")
print("Zensus loading done!")
# filter street net to only use streets thar are longer than 100
#street_net_optimized_gdf = street_net_optimized_gdf[street_net_optimized_gdf["laenge [km]"] >= 0.1]

# buffer street net by buffersize ands create new geodataframe
street_net_optimized_buffered_gdf = street_net_optimized_gdf.copy()
street_net_optimized_buffered_gdf["geometry"] = street_net_optimized_gdf["geometry"].buffer(buffersize)

# buffer pois
pois_buffered_gdf = pois_gdf.copy()
pois_buffered_gdf['geometry'] = pois_gdf.apply(lambda row: row['geometry'].buffer(row['Einflussbereich']), axis=1)

# buffer areas
area_buffered_gdf = area_gdf.copy()
area_buffered_gdf['geometry'] = area_gdf.apply(lambda row: row['geometry'].buffer(row['Einflussbereich']), axis=1)

# buffer 'area of the raster'


# read key-value csv to get klassen und gruppen
poi_key_value_df = pd.read_csv(r"src\data\input\poi_key_value.CSV", sep=";")
list_of_group = list(poi_key_value_df["Gruppe"].unique())
list_of_class = list(poi_key_value_df["Klasse"].unique())

area_key_value_df = pd.read_csv(r"src\data\input\area_key_value.CSV", sep=";")

# append list with unique values
list_of_group.extend(area_key_value_df["Gruppe"].unique())
list_of_class.extend(area_key_value_df["Klasse"].unique())

# create columnsheader
list_of_header = []

for group in list_of_group:
    group_Anzahl_header = group + ": Anzahl"
    group_Summe_bedeutung_header = group + ": Summe_Bedeutung"
    list_of_header.extend([group_Anzahl_header, group_Summe_bedeutung_header])

for klasse in list_of_class:
    klasse_Anzahl_header = klasse + ": Anzahl"
    klasse_Summe_bedeutung_header = klasse + ": Summe_Bedeutung"
    list_of_header.extend([klasse_Anzahl_header, klasse_Summe_bedeutung_header])

# needed columns
for header in list_of_header:
    print(header)
    street_net_optimized_gdf[header] = 0

# Initialize a new column for the sum of values
# Columns with counts
street_net_optimized_gdf['Summe Einwohner'] = 0

'''
# if population improvement applies:
street_net_optimized_gdf['Summe Einwohner (Squares)'] = 0.0
street_net_optimized_gdf['Summe BEV*Bedeutung'] = 0.0
'''
# Columns with Bedeutung
street_net_optimized_gdf['Summe POI*Bedeutung'] = 0
street_net_optimized_gdf['Summe AREA*Bedeutung'] = 0
#street_net_optimized_gdf['Summe Einwohner'] = 0

# Create a spatial index for the census GeoDataFrame
census_sindex = census_gdf.sindex

# Calculate Zensusdensity
for idx, buffered_line in tqdm(street_net_optimized_buffered_gdf.iterrows()):
    possible_matches_index = list(census_sindex.intersection(buffered_line['geometry'].bounds))
    possible_matches = census_gdf.iloc[possible_matches_index]

    intersected_points = possible_matches[possible_matches['geometry'].intersects(buffered_line['geometry'])]
    # assign to id in original gdf
    street_net_optimized_gdf.at[idx, 'Summe Einwohner'] = intersected_points['Einwohner'].sum()

'''
# if population improvement applies:
# per street buffer: sum population and its Bedeutung (= pop * 0.02) 
for idx, buffered_line in tqdm(street_net_optimized_buffered_gdf.iterrows()):
    cand_idx = list(census_sq_sindex.intersection(buffered_line['geometry'].bounds))
    cand = census_sq.iloc[cand_idx]
    touched = cand[cand['geometry'].intersects(buffered_line['geometry'])]

    einw_sq_sum = touched['Einwohner'].sum()
    street_net_optimized_gdf.at[idx, 'Summe Einwohner (Squares)'] = einw_sq_sum
    street_net_optimized_gdf.at[idx, 'Summe BEV*Bedeutung'] = einw_sq_sum * 0.02
'''
# Iterate through lines and update the Summe POI*Bedeutung column
for idx, line in tqdm(street_net_optimized_gdf.iterrows()):
    intersected_pois = pois_buffered_gdf[pois_buffered_gdf['geometry'].intersects(line['geometry'])]
    street_net_optimized_gdf.at[idx, 'Summe POI*Bedeutung'] = intersected_pois['Bedeutung'].sum()

    # count unique groups of intersected_pois dataframe
    group_counts = intersected_pois['Gruppe'].value_counts()
    klasse_counts = intersected_pois['Klasse'].value_counts()

    for group, count in group_counts.items():
        # assign counts
        street_net_optimized_gdf.at[idx, group+": Anzahl"] = count
        # filter intesected pois by group
        intersected_pois_filtert = intersected_pois[intersected_pois["Gruppe"] == group]

        # get sum of Bedeutung in filtered intersected pois
        group_summe_bedeutung = intersected_pois_filtert['Bedeutung'].sum()

        # assign Sum of bedeutung to group
        street_net_optimized_gdf.at[idx, group+": Summe_Bedeutung"] = group_summe_bedeutung

    for klasse, count in klasse_counts.items():
        # assign counts
        street_net_optimized_gdf.at[idx, klasse+": Anzahl"] = count
        # filter intesected pois by klasse
        intersected_pois_filtert = intersected_pois[intersected_pois["Klasse"] == klasse]

        # get sum of Bedeutung in filtered intersected pois
        klasse_summe_bedeutung = intersected_pois_filtert['Bedeutung'].sum()

        # assign Sum of bedeutung to klasse
        street_net_optimized_gdf.at[idx, klasse+": Summe_Bedeutung"] = klasse_summe_bedeutung

# Iterate through lines and update the Summe AREA*Bedeutung column
for idx, line in tqdm(street_net_optimized_gdf.iterrows()):
    intersected_areas = area_buffered_gdf[area_buffered_gdf['geometry'].intersects(line['geometry'])]
    street_net_optimized_gdf.at[idx, 'Summe AREA*Bedeutung'] = intersected_areas['Bedeutung'].sum()

    # count unique groups of intersected_pois dataframe
    group_counts = intersected_areas['Gruppe'].value_counts()
    klasse_counts = intersected_areas['Klasse'].value_counts()

    for group, count in group_counts.items():
        # assign counts
        street_net_optimized_gdf.at[idx, group+": Anzahl"] = count
        # filter intesected pois by group
        intersected_areas_filtert = intersected_areas[intersected_areas["Gruppe"] == group]

        # get sum of Bedeutung in filtered intersected pois
        group_summe_bedeutung = intersected_areas_filtert['Bedeutung'].sum()

        # assign Sum of bedeutung to group
        street_net_optimized_gdf.at[idx, group+": Summe_Bedeutung"] = group_summe_bedeutung

    for klasse, count in klasse_counts.items():
        # assign counts
        street_net_optimized_gdf.at[idx, klasse+": Anzahl"] = count
        # filter intesected pois by klasse
        intersected_areas_filtert = intersected_areas[intersected_areas["Klasse"] == klasse]

        # get sum of Bedeutung in filtered intersected pois
        klasse_summe_bedeutung = intersected_areas_filtert['Bedeutung'].sum()
        street_net_optimized_gdf.at[idx, klasse+": Summe_Bedeutung"] = klasse_summe_bedeutung

# caluculate overall results
street_net_optimized_gdf["Bedeutung je km"] = round(
    (street_net_optimized_gdf["Summe AREA*Bedeutung"] + street_net_optimized_gdf['Summe POI*Bedeutung']) / street_net_optimized_gdf["laenge [km]"], 2)

'''
# if population improvement applies:
# New je-km metric that includes population-based Bedeutung; original stays as-is 
street_net_optimized_gdf['Bedeutung je km (incl Pop)'] = round(
    (
        street_net_optimized_gdf['Summe AREA*Bedeutung']
      + street_net_optimized_gdf['Summe POI*Bedeutung']
      + street_net_optimized_gdf['Summe BEV*Bedeutung (Squares)']
    ) / street_net_optimized_gdf['laenge [km]'],
    2
)
'''

street_net_optimized_gdf["Einwohner je km"] = round(
    street_net_optimized_gdf['Summe Einwohner']/street_net_optimized_gdf["laenge [km]"], 2)

# create Faktor
street_net_optimized_gdf["Einwohner-Faktor"] = round(street_net_optimized_gdf["Einwohner je km"] * 1/15000, 2)
street_net_optimized_gdf["Zaehlstelle"] = ""

# Drop the intermediate column 'intersected_points'


def create_variante1(street_net_optimized_gdf):

    save_gdf_as_gpkg(street_net_optimized_gdf, f"street_net_"+config_data["city_name"], final=True, version="1.9")
    save_gdf_as_gpkg(pois_buffered_gdf, f"buffered_pois_"+config_data["city_name"], final=True, version="1.1")


create_variante1(street_net_optimized_gdf)
street_net_optimized_gdf.to_excel(f""+config_data["city_name"]+'.xlsx',
                                  index=True)  # Save DataFrame to Excel without index
