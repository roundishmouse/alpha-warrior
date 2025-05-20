import requests
from bs4 import BeautifulSoup
import concurrent.futures

def safe_float(text):
    try:
        return float(text.replace(",", "").strip())
    except:
        return 0.0

def fetch_fundamentals(symbol):
    url = f"https://www.screener.in/company/{symbol}/consolidated/"
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")

        # Extract 52w high
        high_52 = 0.0
        table = soup.find("ul", class_="ranges")
        if table:
            for li in table.find_all("li"):
                if "52w High" in li.text:
                    span = li.find_all("span")
                    if span:
                        high_52 = safe_float(span[-1].text)
                    break

        return {
            "symbol": symbol,
            "52w high": high_52
        }

    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
        return {"symbol": symbol, "52w high": 0.0}

def fetch_fundamentals_threaded(symbols):
    fundamentals = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        future_to_symbol = {executor.submit(fetch_fundamentals, symbol): symbol for symbol in symbols}
        for future in concurrent.futures.as_completed(future_to_symbol):
            result = future.result()
            fundamentals.append(result)
            if len(fundamentals) % 10 == 0:
                print(f"Fetched {len(fundamentals)} / {len(symbols)}")
    return fundamentals
