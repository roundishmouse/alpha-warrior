
import os
import time
import pandas as pd
from flask import Flask
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from smartapi.smartconnect import SmartConnect

app = Flask(__name__)

@app.route("/")
def home():
    return "Alpha Warrior Bot + CANSLIM Scraper is Live!"

@app.route("/trigger-alert")
def trigger_alert():
    run_canslim_scraper()
    start_websocket()
    return "Triggered alerts and updated CANSLIM metrics."

def run_canslim_scraper():
    nse_tokens = [
        {'symbol': 'ARE&M'}, {'symbol': 'FACT'}, {'symbol': 'FEDERALBNK'},
        {'symbol': 'RADHIKAWE'}, {'symbol': 'STEELCITY'}, {'symbol': 'ARVSMART'},
        {'symbol': 'RAMRAT'}, {'symbol': 'POWERMECH'}, {'symbol': 'MNC'},
        {'symbol': 'KRBL'}
    ]

    options = Options()
    options.binary_location = "/usr/bin/google-chrome"
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(options=options)

    scraped_data = []

    for stock in nse_tokens:
        symbol = stock['symbol']
        url = f"https://www.screener.in/company/{symbol}/"
        driver.get(url)
        time.sleep(3)

        try:
            roe = driver.find_element(By.XPATH, '//*[@id="top-ratios"]/li[8]/span[2]/span').text
        except:
            roe = "N/A"

        try:
            eps_growth = driver.find_element(By.XPATH, '//*[@id="profit-loss"]/div[4]/table[2]/tbody/tr[4]/td[2]').text
        except:
            eps_growth = "N/A"

        try:
            promoter = driver.find_element(By.XPATH, '//*[@id="quarterly-shp"]/div/table/tbody/tr[1]/td[13]').text
        except:
            promoter = "N/A"

        scraped_data.append({
            'Symbol': symbol,
            'ROE': roe,
            'EPS Growth': eps_growth,
            'Promoter': promoter
        })

    driver.quit()

    df = pd.DataFrame(scraped_data)
    df.to_csv("screener_data.csv", index=False)
    print("CANSLIM data scraped and saved.")

def start_websocket():
    obj = SmartConnect(
        api_key=os.environ.get("SMARTAPI_API_KEY")
    )
    data = obj.generateSession(
        os.environ.get("SMARTAPI_CLIENT_CODE"),
        os.environ.get("SMARTAPI_PASSWORD"),
        os.environ.get("SMARTAPI_TOTP")
    )
    refreshToken = data["data"]["refreshToken"]
    feedToken = obj.getfeedToken()
    print("Login successful")

if __name__ == "__main__":
    start_websocket()
    run_canslim_scraper()
    app.run(host="0.0.0.0", port=81)
