from flask import Flask
from angel_one_api import start_websocket
import requests

app = Flask(__name__)

@app.route("/")
def home():
    return "✅ Quantalgo backend is live."

@app.route("/callback")
def callback():
    return "✅ Callback received from SmartAPI."

@app.route("/my-ip")
def my_ip():
    # Optional: for debugging — gives your server's public IP
    return requests.get("https://ifconfig.me").text

if __name__ == "__main__":
    start_websocket()  # This handles login + WebSocket connection
    app.run(host="0.0.0.0", port=81)
