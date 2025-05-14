import os
import sys
import csv
import time
import pandas as pd
from flask import Flask
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from angel_one_api import start_websocket
from nse_token_data import nse_tokens

app = Flask(__name__)

@app.route("/")
def home():
    return "Alpha Warrior Bot with CANSLIM is Live!"

@app.route("/callback")
def callback():
    return "Callback received from SmartAPI."

@app.route("/trigger-alert")
def trigger_alert():
    run_canslim_scraper()
    start_websocket()
    return "Triggered alerts and updated CANSLIM metrics."

def run_canslim_scraper():
    options = Options()
    options.binary_location = "/usr/bin/google-chrome"
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(service=Service("chromedriver"), options=options)
    data = []

    for token in nse_tokens:
        symbol = token["symbol"]
        url = f"https://www.screener.in/company/{symbol}/consolidated/"
        driver.get(url)
        time.sleep(2)

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

        data.append({
            "Symbol": symbol,
            "ROE": roe,
            "EPS Growth": eps_growth,
            "Promoter": promoter
        })

    driver.quit()

    df = pd.DataFrame(data)
    df.to_csv("screener_data.csv", index=False)

if __name__ == "__main__":
    start_websocket()
    app.run(host="0.0.0.0", port=81)
