import time

import openmeteo_requests
import pandas as pd
import requests
import requests_cache
from retry_requests import retry
from utils.config_loader import config_data


# Function to get latitude and longitude by city name using OpenWeatherMap API
def get_coordinates(city_name, api_key):
    """
    Retrieves the latitude and longitude coordinates of a city using the OpenWeatherMap API.

    Args:
        city_name (str): Name of the city for which coordinates are requested.
        api_key (str): API key for accessing the OpenWeatherMap API.

    Returns:
        tuple: A tuple containing the latitude and longitude coordinates of the city. This is used in the OpenMeteo API

    Raises:
        requests.exceptions.RequestException: If an error occurs during the API request.
        ValueError: If no results are found for the specified city.
    """
    url = f"http://api.openweathermap.org/geo/1.0/direct?q={city_name}&limit=1&appid={api_key}"
    try:
        response = requests.get(url)
        response.raise_for_status()  # Check if the request was successful
        data = response.json()
        
        if not data:
            raise ValueError(f"No results found for city: {city_name}")
        
        return float(data[0]['lat']), float(data[0]['lon'])
    
    except requests.exceptions.RequestException as e:
        print(f"Request error for city {city_name}: {e}")
        raise
    except ValueError as e:
        print(f"Value error for city {city_name}: {e}")
        raise

# Function to fetch weather data and calculate the average temperature, humidity, and precipitation
# Function to fetch weather data and calculate the average temperature, humidity, and precipitation
def get_weather_data(latitude, longitude, date, timezone="Europe/Berlin"):
    """
    Retrieves historical weather data (average temperature, humidity, and precipitation) for a specific date and location using the OpenMeteo API.

    Args:
        latitude (float): Latitude of the location.
        longitude (float): Longitude of the location.
        date (datetime): Date for which weather data is requested.
        timezone (str, optional): Timezone for the location. Defaults to "Europe/Berlin".

    Returns:
        tuple: A tuple containing the average temperature, humidity, and precipitation.

    Raises:
        Exception: If an error occurs during the data retrieval process.
    """
    # IMPORTANT INFORMATION
    # Non-Commercial Use
    # By using the Free API for non-commercial use you agree to following terms:
    # Less than 10'000 API calls per day, 5'000 per hour and 600 per minute.
    # You may only use the free API services for non-commercial purposes.
    # You accept to the CC-BY 4.0 license, as specified in the license conditions.
    # We reserve the right to block applications and IP addresses that misuse our service without prior notice.
    # see also: https://open-meteo.com/en/terms
    
    cache_session = requests_cache.CachedSession('.cache', expire_after=3600)
    retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
    openmeteo = openmeteo_requests.Client(session=retry_session)
    
    url = "https://historical-forecast-api.open-meteo.com/v1/forecast"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": date.strftime('%Y-%m-%d'),
        "end_date": date.strftime('%Y-%m-%d'),
        "hourly": ["temperature_2m", "relative_humidity_2m", "precipitation"],
        "timezone": timezone
    }
    
    try:
        responses = openmeteo.weather_api(url, params=params)
        response = responses[0]
        
        hourly = response.Hourly()
        hourly_temperature_2m = hourly.Variables(0).ValuesAsNumpy() # type: ignore
        hourly_relative_humidity_2m = hourly.Variables(1).ValuesAsNumpy() # type: ignore
        hourly_precipitation = hourly.Variables(2).ValuesAsNumpy()  # type: ignore
        
        average_temperature = hourly_temperature_2m.mean() # type: ignore
        average_humidity = hourly_relative_humidity_2m.mean() # type: ignore
        average_precipitation = hourly_precipitation.mean()  # type: ignore
        
        return average_temperature, average_humidity, average_precipitation
    
    except Exception as e:
        print(f"Error fetching weather data for coordinates ({latitude}, {longitude}) on {date}: {e}")
        raise

def recieve_weather_data(df, api_key):
    """
    Receives weather data for cities from a DataFrame, retrieves corresponding coordinates, fetches historical weather data, and saves the results to CSV and Excel files.

    Args:
        df (DataFrame): Input DataFrame containing 'Stadt' and 'Datum' columns.
        api_key (str): API key for accessing location data.

    Returns:
        None

    Raises:
        ValueError: If an error occurs during the data retrieval process.

    Examples:
        recieve_weather_data(df, 'your_api_key')
    """
    # Type hints for DataFrame columns
    assert 'Stadt' in df.columns and 'Datum' in df.columns, "DataFrame must contain 'Stadt' and 'Datum' columns"
    assert pd.api.types.is_datetime64_any_dtype(df['Datum']), "'Datum' column must be of datetime64[ns] dtype"
    
    # Initialize a list to store the results
    results = []
    if api_key:
        # Iterate through the DataFrame
        for index, row in df.iterrows():
            city = row['Stadt']
            date = pd.to_datetime(row['Datum'])  # Ensure the date is in datetime format

            try:
                latitude, longitude = get_coordinates(city, api_key)
                print(f"Coordinates for {city}: {latitude}°N, {longitude}°E")
                average_temperature, average_humidity, average_precipitation = get_weather_data(latitude, longitude, date)

                # Store the results
                results.append({
                    "city": city,
                    "date": date.strftime('%Y-%m-%d'),
                    "average_temperature": average_temperature,
                    "average_humidity": average_humidity,
                    "average_precipitation": average_precipitation
                })

                time.sleep(1)  # Add delay to avoid rate limiting
            except ValueError as e:
                print(f"Error for city {city}: {e}")

        # Create a DataFrame from the results
        if results:
            final_df = pd.DataFrame(results)
            # List of specific columns to update
            columns_to_update = ['average_temperature', 'average_humidity', 'average_precipitation']
            final_df[columns_to_update] = final_df[columns_to_update].astype(str)
            # Replace '.' with ',' in the values of the specified columns
            final_df[columns_to_update] = final_df[columns_to_update].map(lambda x: x.replace('.', ','))       

            # Save the final DataFrame to a CSV file
            final_df.to_csv('weather_averages.csv', index=False)
            final_df.to_excel('weather_averages.xlsx', index=False)
            print("Data saved to weather_averages.csv")
        else:
            print("No data fetched.") 
    else:
        print("Invalid Api_key, go to config.yaml and insert personal api_key from openweathermap") 
def main():
    
    filepath = r"Z:_Public\Projekte\IVST\058_FoPS_Fuss\02_Bearbeitung\AP5\Matrix_Zählstellen_kategorisiert_geclustered_Auswahl_unskaliert.xlsx"
    df = pd.read_excel(filepath)
    print(df.info())
    print(df["Datum"])

# Replace with your OpenWeatherMap API key 
    api_key = config_data["openweatherapi_key"]
    
    recieve_weather_data(df, api_key)

if __name__ == "__main__":
    main()
