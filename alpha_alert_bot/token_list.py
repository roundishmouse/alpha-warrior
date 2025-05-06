import pandas as pd

def final_top_picks():
    df = pd.read_csv("nse_tokens.csv")
    return df.to_dict(orient="records")
