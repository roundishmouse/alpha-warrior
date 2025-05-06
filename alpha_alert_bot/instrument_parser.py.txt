import pandas as pd
import requests
from io import StringIO

def get_nse_tokens():
    url = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.csv"
    response = requests.get(url)
    if response.status_code != 200:
        raise Exception("Failed to fetch instrument master")

    data = pd.read_csv(StringIO(response.text))
    data = data[data['exchange'] == 'NSE']
    tokens = data['token'].astype(str).unique().tolist()
    return tokens
