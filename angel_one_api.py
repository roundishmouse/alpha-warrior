import pandas as pd
import requests

def get_top_stocks(token):
    # Fetch real or sample stock data
    df = pd.read_csv("https://raw.githubusercontent.com/roundishmouse/nse-data/main/sample-stock-data.csv")

    # Filter 1: Avoid penny stocks
    df = df[df["price"] > 100]

    # Filter 2: Within 25% of 52-week high
    df["distance_from_high"] = 1 - (df["price"] / df["52_week_high"])
    df = df[df["distance_from_high"] <= 0.25]

    # Filter 3: Volume spike (current volume at least 1.2× 50-day average)
    df["volume_spike"] = df["volume"] / df["avg_volume_50d"]
    df = df[df["volume_spike"] >= 1.2]

    # Momentum score based on 3-month price growth
    df["momentum"] = df["price"] / df["price_3m_ago"] - 1

    # Final score: momentum * 100
    df["score"] = df["momentum"] * 100

    # Sort and return top 2
    top_stocks = df.sort_values(by="score", ascending=False).head(2)
    
    # Fallback: If no stock passes, return message
    if top_stocks.empty:
        return [{"symbol": "No picks", "score": 0}]

    return top_stocks[["symbol", "score"]].to_dict(orient="records")
