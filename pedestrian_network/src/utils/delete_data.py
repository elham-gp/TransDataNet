import os


def delete_downloaded_zensusfile():
# Directory path
    directory_path = "data/input/zensusfile"

    # List all files in the directory
    files = os.listdir(directory_path)

    # Iterate through the files and delete those matching the pattern
    for file in files:
        file_path = os.path.join(directory_path, file)
        os.remove(file_path)
        print(f"File '{file}' deleted successfully.")