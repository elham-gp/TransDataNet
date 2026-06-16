import geopandas as gpd
import pandas as pd
from tqdm import tqdm
import os


def load_geopackage():
    # Pfad zur GeoPackage-Datei
    geopackage_path = r"src\data\output\Seitendaten\Seitendaten.gpkg"
    # Laden des GeoPackages (mit Angabe der Ebene/Layer)
    return gpd.read_file(geopackage_path)

def load_all_poi_gdf():
    list_of_poi_gdf = []
    mainfolder = r"C:\Users\Goerner\Desktop\poi_geopackages"
    for geopackage in os.listdir(mainfolder):
        filepath = os.path.join(mainfolder, geopackage)
        poi_gdf = gpd.read_file(filepath)
        list_of_poi_gdf.append(poi_gdf)
    return list_of_poi_gdf


def create_columnhead(streetside_polygon_gdf):
    
    # create columnsheader
    list_of_header = []

    # read key-value csv to get klassen und gruppen
    poi_key_value_df = pd.read_csv(r"src\data\input\poi_key_value.CSV", sep=";")
    list_of_group = list(poi_key_value_df["Gruppe"].unique())
    list_of_class = list(poi_key_value_df["Klasse"].unique())

    area_key_value_df = pd.read_csv(r"src\data\input\area_key_value.CSV", sep=";")

    # append list with unique values
    list_of_group.extend(area_key_value_df["Gruppe"].unique())
    list_of_class.extend(area_key_value_df["Klasse"].unique())
    
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
        streetside_polygon_gdf[header] = 0
    return streetside_polygon_gdf

def iterate_through_polygon(streetside_polygon_gdf, list_of_poi_gdf):
    # iterate through polygons
    i = 0
    for idx_p, polygon in tqdm(streetside_polygon_gdf.iterrows()):       
        for poi_gdf in list_of_poi_gdf:
            intersected_pois_gdf = poi_gdf[poi_gdf['geometry'].intersects(polygon['geometry'])]
            if not intersected_pois_gdf.empty:
                
                # count unique groups of intersected_pois dataframe
                group_counts = intersected_pois_gdf['Gruppe'].value_counts()
                klasse_counts = intersected_pois_gdf['Klasse'].value_counts()

                for group, count in group_counts.items():
                #     # assign counts
 
                    streetside_polygon_gdf.at[idx_p, group+": Anzahl"] = count
                #   filter intesected pois by group
                    intersected_pois_gdf_filtered = intersected_pois_gdf[intersected_pois_gdf["Gruppe"] == group]
                    #print(intersected_pois_gdf)
                #     # get sum of Bedeutung in filtered intersected pois
                    
                    group_summe_bedeutung = intersected_pois_gdf_filtered['Bedeutung'].sum()

                #    assign Sum of bedeutung to group
                    streetside_polygon_gdf.at[idx_p, group+": Summe_Bedeutung"] = group_summe_bedeutung

                for klasse, count in klasse_counts.items():
                #     # assign counts
                    streetside_polygon_gdf.at[idx_p, klasse+": Anzahl"] = count
                #     # filter intesected pois by klasse
                #     intersected_pois_gdf = intersected_pois_gdf[intersected_pois_gdf["Klasse"] == klasse]

                #     # get sum of Bedeutung in filtered intersected pois
                    intersected_pois_gdf_filtered = intersected_pois_gdf[intersected_pois_gdf["Klasse"] == klasse]
                    klasse_summe_bedeutung = intersected_pois_gdf_filtered['Bedeutung'].sum()
                    print(intersected_pois_gdf['Bedeutung'])
                    print(klasse_summe_bedeutung)
                    streetside_polygon_gdf.at[idx_p, klasse+": Summe_Bedeutung"] = klasse_summe_bedeutung
                    
    #print(streetside_polygon_gdf)

    # Save as Excel file
    streetside_polygon_gdf.to_excel("output.xlsx", index=False)
    
    
def iterate_through_polygon2(polygon_gdf, points_gdf):
    # Perform a spatial join between the points and polygons
    joined = gpd.sjoin(points_gdf, polygon_gdf, how="inner", predicate="within")

    # Count points in each polygon
    counts = joined.groupby('index_right').size()

    # Add the counts back to the original polygon GeoDataFrame
    polygon_gdf['point_count'] = polygon_gdf.index.map(counts).fillna(0).astype(int)
    print(polygon_gdf)



def main():
    streetside_polygon_gdf = load_geopackage()
    streetside_polygon_gdf = create_columnhead(streetside_polygon_gdf)
    list_of_pois_gdf = load_all_poi_gdf()
           
    iterate_through_polygon(streetside_polygon_gdf, list_of_pois_gdf)


if __name__ == "__main__":
    main()
