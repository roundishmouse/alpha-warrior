import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask import Flask
from angel_one_api import start_websocket

app = Flask(__name__)

@app.route("/")
def home():
    return "Alpha Warrior Bot is Live!"

@app.route("/callback")
def callback():
    return "✅ Callback received from SmartAPI."

@app.route("/my-ip")
def get_ip():
    import requests
    return requests.get("https://api64.ipify.org").text

# New route for cron job to trigger alerts
@app.route("/trigger-alert")
def trigger_alert():
    start_websocket()
    return "Quant bot triggered by cron"

if __name__ == "__main__":
    print("✓ Sending login request...")
    start_websocket()
    app.run(host="0.0.0.0", port=81)
