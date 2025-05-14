
import os
import sys
import time
import pandas as pd
from flask import Flask
from angel_one_api import start_websocket
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By

# Append path for importing sibling modules if needed
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

# Flask app for SmartAPI integration
app = Flask(__name__)

@app.route("/")
def home():
    return "Alpha Warrior Bot is Live!"

@app.route("/callback")
def callback():
    return "Callback received from SmartAPI."

@app.route("/trigger-alert")
def trigger_alert():
    start_websocket()
    return "Quant bot triggered by cron"

# CANSLIM Screener Function
def run_canslim_screener():
    from nse_token_data import nse_tokens

    chrome_service = Service("chromedriver.exe")
    driver = webdriver.Chrome(service=chrome_service)

    results = []

    for token in nse_tokens:
        symbol = token['symbol']
        url = f"https://www.screener.in/company/{symbol}/"

        driver.get(url)
        time.sleep(3)

        # ROE
        try:
            roe = driver.find_element(By.XPATH, '//li[span[text()="ROE"]]').text
        except:
            roe = "N/A"

        # Promoter Holding
        try:
            driver.get(url + "shareholding/")
            time.sleep(2)
            promoter = driver.find_element(By.XPATH, '//*[@id="shareholding"]/div[1]/table/tbody/tr[1]/td[13]').text
        except:
            promoter = "N/A"

        # EPS Growth (3Y)
        try:
            driver.get(url + "profit-loss/")
            time.sleep(2)
            eps_growth = driver.find_element(By.XPATH, '//*[@id="profit-loss"]/div[4]/table[2]/tbody/tr[4]/td[2]').text
        except:
            eps_growth = "N/A"

        results.append({
            "Symbol": symbol,
            "ROE": roe,
            "EPS Growth": eps_growth,
            "Promoter Holding": promoter
        })

    driver.quit()
    df = pd.DataFrame(results)
    df.to_csv("screener_data.csv", index=False)
    print("CANSLIM Screener Completed. Data saved to screener_data.csv")

# Run Screener on Startup
run_canslim_screener()

# Start Flask and SmartAPI bot
if __name__ == "__main__":
    print("Launching Alpha Warrior CANSLIM Bot...")
    start_websocket()
    app.run(host="0.0.0.0", port=81)
