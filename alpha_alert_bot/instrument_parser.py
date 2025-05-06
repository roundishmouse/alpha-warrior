import pandas as pd
import requests
from io import StringIO

def get_token_for_symbols(symbols, exchange="NSE"):
    url = "https://margincalc.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.csv"
    response = requests.get(url)
    if response.status_code != 200:
        raise Exception("Failed to fetch instrument master")

    data = pd.read_csv(StringIO(response.text))
    data = data[(data["symbol"].isin(symbols)) & (data["exch_seg"] == exchange)]
    return data["token"].astype(str).unique().tolist()

