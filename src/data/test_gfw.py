import requests
import os
import json

base_url = "https://data-api.globalforestwatch.org"
api_key = "02c4071f-8657-4490-92eb-f0588aa0e082"
dataset = "gfw_integrated_alerts"

def get_versions():
    url = f"{base_url}/dataset/{dataset}"
    r = requests.get(url)
    if r.status_code == 200:
        data = r.json().get("data", {})
        versions = data.get("versions", [])
        print(f"Versions: {versions}")
        return versions
    return []

if __name__ == "__main__":
    get_versions()
