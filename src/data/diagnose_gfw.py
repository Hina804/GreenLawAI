# diagnose_gfw.py
import requests
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GFW_API_KEY")
base_url = "https://data-api.globalforestwatch.org"
dataset_id = "gfw_integrated_alerts"

def diagnose():
    url = f"{base_url}/dataset/{dataset_id}"
    response = requests.get(url, timeout=10)
    versions = response.json().get("data", {}).get("versions", [])
    print(f"Total versions: {len(versions)}")
    
    # Try the last 10 versions
    for v in sorted(versions, reverse=True)[:10]:
        print(f"\nChecking version: {v}")
        fields_url = f"{base_url}/dataset/{dataset_id}/{v}/fields"
        rf = requests.get(fields_url, timeout=5)
        if rf.status_code != 200:
            print(f"  Fields check failed: {rf.status_code}")
            continue
            
        fields = [f.get('pixel_meaning') for f in rf.json().get("data", [])]
        date_col = 'gfw_integrated_dist_alerts__date' if 'gfw_integrated_dist_alerts__date' in fields else 'gfw_integrated_alerts__date'
        print(f"  Detected date_col: {date_col}")
        
        query_url = f"{base_url}/dataset/{dataset_id}/{v}/query"
        sql = f"SELECT latitude, longitude, {date_col} FROM results LIMIT 5"
        headers = {"x-api-key": api_key, "Content-Type": "application/json"}
        rq = requests.post(query_url, json={"sql": sql}, headers=headers, timeout=10)
        
        if rq.status_code == 200:
            data = rq.json().get("data", [])
            print(f"  SUCCESS! Records found: {len(data)}")
            if data:
                print(f"  Sample Date: {data[0].get(date_col)}")
        else:
            print(f"  Query failed: {rq.status_code} - {rq.text[:100]}")

if __name__ == "__main__":
    diagnose()
