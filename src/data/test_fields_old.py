import requests
import json

base_url = "https://data-api.globalforestwatch.org"
dataset = "gfw_integrated_alerts"
version = "v20260318"

def check():
    url = f"{base_url}/dataset/{dataset}/{version}/fields"
    r = requests.get(url)
    print(f"Status: {r.status_code}")
    if r.status_code == 200:
        fields = r.json().get("data", [])
        field_names = [f.get('pixel_meaning') for f in fields]
        print(f"Fields for {version}: {field_names}")

if __name__ == "__main__":
    check()
