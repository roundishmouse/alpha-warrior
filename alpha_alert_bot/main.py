
from flask import Flask
from angel_one_api import start_websocket

app = Flask(__name__)

@app.route("/")
def home():
    return "Alpha Warrior Bot is Live!"

@app.route("/trigger-alert")
def trigger():
    start_websocket()
    return "✅ Alert Triggered Successfully"

if __name__ == "__main__":
    print("⏳ Starting Alpha Warrior Bot...")
    start_websocket()
    app.run(host="0.0.0.0", port=81)
