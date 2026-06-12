# config_loader.py
import yaml


def load_config(file_path='config.yml'):
    with open(file_path, 'r',encoding="utf-8") as file:
        return yaml.safe_load(file)

# Load the configuration once when the module is imported
config_data = load_config()

