import os
import requests
from dotenv import load_dotenv

def test():
    load_dotenv()
    api_key = os.getenv("GFW_API_KEY")
    v = 'v20260311'
    base = 'https://data-api.globalforestwatch.org/dataset/gfw_integrated_alerts'
    
    # 1. Check Fields
    r_f = requests.get(f'{base}/{v}/fields')
    if r_f.status_code != 200:
        print(f"Version {v} fields check failed: {r_f.status_code}")
        return
    
    fields = [f['pixel_meaning'] for f in r_f.json().get('data', [])]
    date_col = 'gfw_integrated_dist_alerts__date' if 'gfw_integrated_dist_alerts__date' in fields else 'gfw_integrated_alerts__date'
    print(f"Date column: {date_col}")
    
    # 2. Query with Geometry (Broad Box: 70-76E, 31-37N)
    geom = {
        "type": "Polygon",
        "coordinates": [[[70.0, 31.0], [76.0, 31.0], [76.0, 37.0], [70.0, 37.0], [70.0, 31.0]]]
    }
    sql = f"SELECT latitude, longitude, {date_col} FROM results LIMIT 100"
    
    r_q = requests.post(f'{base}/{v}/query', 
                        json={'sql': sql, 'geometry': geom}, 
                        headers={'Content-Type': 'application/json', 'x-api-key': api_key})
    
    print(f"Query Status: {r_q.status_code}")
    if r_q.status_code == 200:
        data = r_q.json().get('data', [])
        print(f"Records found: {len(data)}")
        if data:
            print(f"Sample: {data[0]}")
    else:
        print(f"Error: {r_q.text}")

if __name__ == "__main__":
    test()
