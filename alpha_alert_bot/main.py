from flask import Flask
from angel_one_api import start_websocket

app = Flask(__name__)

@app.route("/")
def home():
    return "Alpha Warrior Bot is Live!"

if __name__ == "__main__":
    start_websocket()
    app.run(host="0.0.0.0", port=81)
