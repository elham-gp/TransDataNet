import inspect
import json
import os

from datetime import datetime
from .config_loader import config_data


def save_metadata(file_path, version=None, stage=None, description="Description of the contents", function_name=None):
    """
    Creates and saves a metadata file for the given GeoDataFrame.

    Parameters:
        file_path (str): The path to the GeoPackage file.
        gdf (gpd.GeoDataFrame): The GeoDataFrame for which metadata is being created.
        version (str, optional): The version of the dataset.
        stage (str, optional): The stage of the dataset (e.g., 'draft').
        description (str, optional): A description of the contents. Defaults to "Description of the contents".

    Returns:
        None
    """
    # Extract directory and filename without extension
    directory = os.path.dirname(file_path)
    filename = os.path.basename(file_path).replace('.gpkg', '')

    # Create metadata
    metadata = {
        "filename": filename,
        "creation_date": datetime.now().isoformat(),
        "version": version,
        "stage": stage,
        "description": description,
        "used in function:" : function_name
    }

    # Save metadata to a JSON file
    metadata_path = os.path.join(directory, f"{filename}.json")
    with open(metadata_path, 'w') as metadata_file:
        json.dump(metadata, metadata_file, indent=4)
    print(f"Metadata saved at {metadata_path}")

def save_gdf_as_gpkg(gdf, filename: str,   final: bool = False, version: str = "", interimresult: bool = False): # 
    """
    Saves a GeoDataFrame to a GeoPackage file, automatically setting the stage to 'draft' unless it is None,
    and handling different versions and interim results.

    Parameters:
        gdf (gpd.GeoDataFrame): The GeoDataFrame to save.
        filename (str): The name of the output file without extension.
        version (str, optional): Version of the dataset, appended to the filename.
        stage (str, optional): If not None, stage is set to 'draft'.
        interimresult (bool, optional): If True and saving interim results is enabled,
                                        sets the stage to 'interim'.

    Returns: None
    """
    city = config_data["city_name"]
    save_interim_results = config_data["save_interim_results"]

    if interimresult and not save_interim_results:
        print(f"Skipping save of {filename} due to configuration settings.")
        return

    # Automatically set stage to 'draft' if it is not None
    # Automatically set stage to 'draft' if final is False
    if final:
        stage = None
    else:
        stage = 'draft'

    if interimresult and save_interim_results:
        stage = 'interim'

    # Handle filename with version
    filename_with_version = f"{filename}_v{version}.gpkg" if version else f"{filename}.gpkg"

    # Determine the directory path
    directory = f"src/data/output/{city}"
    
    
    if stage:
        directory = os.path.join(directory, stage)  # Append stage if it's not None
        
    # Ensure the directory exists
    os.makedirs(directory, exist_ok=True)
    file_path = os.path.join(directory, filename_with_version)
    


    # Save the GeoDataFrame
    gdf.to_file(file_path, driver='GPKG')
    print(f"File saved at {file_path}")
    
    
    calling_function_name = inspect.stack()[1].function
    # Save metadata
    save_metadata(file_path, version, stage,function_name= calling_function_name)