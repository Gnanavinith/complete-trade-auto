"""
Keep-Alive Ping Script for Render Server.
Pings the backend /health endpoint every 10 minutes to prevent the free tier container from sleeping.
"""
import time
import requests
from datetime import datetime

URL = "https://complete-trade-auto.onrender.com/status"
INTERVAL_SECONDS = 600  # 10 minutes (Render spins down after 15 minutes)

def ping():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        res = requests.get(URL, timeout=45)
        print(f"[{now}] Ping {URL} -> Status: {res.status_code}")
    except Exception as e:
        print(f"[{now}] Ping failed (server may be waking up): {e}")

if __name__ == "__main__":
    print(f"Starting Keep-Alive monitor for {URL}")
    print(f"Pinging every {INTERVAL_SECONDS // 60} minutes...\n")
    while True:
        ping()
        time.sleep(INTERVAL_SECONDS)
