import requests
from bs4 import BeautifulSoup
import concurrent.futures

def fetch_fundamentals(symbol):
    url = f"https://www.screener.in/company/{symbol}/consolidated/"
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")

        # Extract 52w high
        table = soup.find("ul", class_="ranges")
        items = table.find_all("li") if table else []
        high_52 = 0

        for li in items:
            if "52w High" in li.text:
                try:
                    span_text = li.find_all("span")[-1].text.strip().replace(",", "")
                    high_52 = float(span_text)
                except:
                    high_52 = 0
                break

        return {
            "symbol": symbol,
            "52w high": high_52
        }

    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
        return {"symbol": symbol, "52w high": 0}

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
