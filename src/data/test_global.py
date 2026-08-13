import requests
import os
import json

base_url = "https://data-api.globalforestwatch.org"
api_key = "02c4071f-8657-4490-92eb-f0588aa0e082"
dataset = "gfw_integrated_alerts"
version = "v20260326"
date_col = "gfw_integrated_dist_alerts__date"

def global_check():
    url = f"{base_url}/dataset/{dataset}/{version}/query"
    # Basic query, no geometry
    sql = f"SELECT latitude, longitude, {date_col} FROM results LIMIT 1"
    headers = {"x-api-key": api_key, "Content-Type": "application/json"}
    r = requests.post(url, json={"sql": sql}, headers=headers)
    print(f"Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json().get("data", [])
        print(f"Global Data Sample: {data}")

if __name__ == "__main__":
    global_check()
