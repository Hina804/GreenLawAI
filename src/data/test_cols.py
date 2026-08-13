import requests
import json

base_url = "https://data-api.globalforestwatch.org"
dataset = "gfw_integrated_alerts"
version = "v20260318"

def check():
    url = f"{base_url}/dataset/{dataset}/{version}/query"
    api_key = "02c4071f-8657-4490-92eb-f0588aa0e082"
    sql = "SELECT * FROM results LIMIT 1"
    headers = {"x-api-key": api_key, "Content-Type": "application/json"}
    r = requests.post(url, json={"sql": sql}, headers=headers)
    print(f"Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json().get("data", [])
        if data:
            print(f"Columns: {list(data[0].keys())}")

if __name__ == "__main__":
    check()
