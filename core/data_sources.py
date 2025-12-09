import time
import random
import requests
import pandas as pd
from datetime import datetime

# Public demo endpoint for market data (no API key)
COINGECKO_BTC_URL = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"


def fetch_coingecko_btc_usd(days: int = 1, interval: str = "hourly") -> pd.DataFrame:
    try:
        params = {"vs_currency": "usd", "days": days, "interval": interval}
        r = requests.get(COINGECKO_BTC_URL, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        prices = data.get("prices", [])
        df = pd.DataFrame(prices, columns=["ts_ms", "price_usd"])
        if df.empty:
            return df
        df["ts"] = pd.to_datetime(df["ts_ms"], unit="ms")
        df = df.drop(columns=["ts_ms"]) [["ts", "price_usd"]]
        return df
    except Exception:
        # Fallback to synthetic data
        now = datetime.utcnow()
        ts = pd.date_range(end=now, periods=24, freq="H")
        price = 30000 + pd.Series(range(24)).cumsum() * 5 + pd.Series(
            [random.gauss(0, 50) for _ in range(24)]
        )
        return pd.DataFrame({"ts": ts, "price_usd": price})


def generate_iot_sensor_frame(n_sensors: int = 25) -> pd.DataFrame:
    # Create a grid of sensors with synthetic readings
    side = int(n_sensors ** 0.5)
    side = max(side, 3)
    grid = [(i, j) for i in range(side) for j in range(side)]
    values = [random.gauss(50, 10) for _ in grid]
    ts = datetime.utcnow()
    df = pd.DataFrame(grid, columns=["row", "col"])
    df["value"] = values
    df["ts"] = ts
    return df


def simulate_social_stream(n: int = 50) -> pd.DataFrame:
    topics = ["#AI", "#BigData", "#IoT", "#Analytics", "#ML"]
    data = []
    now = datetime.utcnow()
    for i in range(n):
        data.append(
            {
                "ts": now,
                "text": f"Post {i} about {random.choice(topics)}",
                "sentiment": random.choice(["pos", "neu", "neg"]),
                "engagement": random.randint(0, 1000),
            }
        )
    return pd.DataFrame(data)
