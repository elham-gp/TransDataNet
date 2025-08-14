'''
# utils/osm_config.py
import os
import datetime as dt
import osmnx as ox

def configure():
    # Helpful logs + caching
    ox.settings.log_console = True
    ox.settings.use_cache = True
    ox.settings.cache_folder = "./cache"

    # Nominatim requires a custom User-Agent that identifies your app + contact.
    # We read it from an env var so you don't commit your personal email.
    fallback_ua = (
        f"pedestrian_network/{dt.date.today().isoformat()} "
        "(+https://github.com/hgoerner/pedestrian_network; "
        "contact: https://github.com/hgoerner/pedestrian_network/issues)"
    )
    ox.settings.default_user_agent = os.getenv("OX_USER_AGENT", fallback_ua)

    # Overpass tuning (can override via env vars)
    ox.settings.overpass_endpoint   = os.getenv("OVERPASS_ENDPOINT", "https://overpass-api.de/api")
    ox.settings.overpass_rate_limit = True
    ox.settings.overpass_timeout    = int(os.getenv("OVERPASS_TIMEOUT", "240"))          # seconds
    ox.settings.overpass_memory     = int(os.getenv("OVERPASS_MEMORY",  str(2*1024*1024*1024)))  # bytes
    ox.settings.max_query_area_size = float(os.getenv("OX_MAX_QUERY_AREA", "1e7"))       # m²; lower → smaller tiles

'''
# utils/osm_config.py
import os, datetime as dt, osmnx as ox

def configure():
    # Allow overriding via env vars
    project_url = os.getenv("OX_PROJECT_URL", "https://github.com/hgoerner/pedestrian_network")
    contact     = os.getenv("OX_CONTACT",     "https://github.com/hgoerner/pedestrian_network/issues")

    # Final UA: explicit OX_USER_AGENT wins; otherwise build one from URL + contact
    fallback_ua = f"pedestrian_network/{dt.date.today().isoformat()} (+https://github.com/hgoerner/pedestrian_network; contact: elhamgolpayegani76#gmail.com)"
    ox.settings.default_user_agent = os.getenv("OX_USER_AGENT", fallback_ua)

    # Overpass/Nominatim friendliness
    ox.settings.use_cache = True
    ox.settings.cache_folder = "./cache"
    ox.settings.overpass_endpoint   = os.getenv("OVERPASS_ENDPOINT", "https://overpass.kumi.systems/api")
    ox.settings.overpass_rate_limit = True
    ox.settings.overpass_timeout    = int(os.getenv("OVERPASS_TIMEOUT", "240"))
    ox.settings.overpass_memory     = int(os.getenv("OVERPASS_MEMORY",  str(2*1024*1024*1024)))
    ox.settings.max_query_area_size = float(os.getenv("OX_MAX_QUERY_AREA", "1e7"))
