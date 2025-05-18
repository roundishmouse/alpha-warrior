import requests
import time
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup

CACHE_FILE = "screener_cache.json"
CACHE_EXPIRY_HOURS = 24

headers = {
    "User-Agent": "Mozilla/5.0"
}

def fetch_data(symbol):
    url = f"https://www.screener.in/company/{symbol}/consolidated/"
    try:
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")

        roe_tag = soup.find(text="Return on capital employed")
        roe = roe_tag.find_next().text.strip().replace("%", "") if roe_tag else None

        eps_tag = soup.find(text="Compounded Profit Growth")
        eps = eps_tag.find_next().text.strip().replace("%", "") if eps_tag else None

        high_tag = soup.find(text="High")
        high = high_tag.find_next().text.strip().replace("₹", "").replace(",", "") if high_tag else None

        return {
            "symbol": symbol,
            "roe": roe,
            "eps_growth": eps,
            "52w_high": high
        }
    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
        return None

def is_cache_valid():
    if not os.path.exists(CACHE_FILE):
        return False
    modified = os.path.getmtime(CACHE_FILE)
    return (time.time() - modified) < (CACHE_EXPIRY_HOURS * 3600)

def load_cache():
    with open(CACHE_FILE, "r") as f:
        return json.load(f)

def save_cache(data):
    with open(CACHE_FILE, "w") as f:
        json.dump(data, f, indent=2)

def scrape_all(symbols, max_threads=10):
    all_data = []
    with ThreadPoolExecutor(max_threads) as executor:
        futures = {executor.submit(fetch_data, sym): sym for sym in symbols}
        for future in as_completed(futures):
            result = future.result()
            if result:
                all_data.append(result)
    save_cache(all_data)
    return all_data

def get_fundamental_data(symbols):
    if is_cache_valid():
        print("Using cached Screener data...")
        return load_cache()
    else:
        print("Fetching fresh Screener data...")
        return scrape_all(symbols)