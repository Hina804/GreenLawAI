# create_gfw_api_key_fixed.py
import requests
import json

# Read token from file
try:
    with open("gfw_token.txt", "r") as f:
        ACCESS_TOKEN = f.read().strip()
    print(f"✅ Token loaded (length: {len(ACCESS_TOKEN)})")
except:
    ACCESS_TOKEN = input("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6IjY5YzEyMTU4N2YyNmJlZmFmMTU5ZjllYiIsInJvbGUiOiJVU0VSIiwicHJvdmlkZXIiOiJsb2NhbCIsImVtYWlsIjoiYXFhbGkucGs5MkBnbWFpbC5jb20iLCJleHRyYVVzZXJEYXRhIjp7ImFwcHMiOlsicnciXX0sImNyZWF0ZWRBdCI6MTc3NDY5Nzg2ODg4MywiaWF0IjoxNzc0Njk3ODY4fQ.9J7T0nPui4w8GiBt8VSUCwHhHzwyLpB4GyUqTZFkUOg")

print("\n📝 Creating API Key...")
print("-" * 40)

headers = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json"
}

data = {
    "alias": "GreenLawAI-Forest-Monitor",
    "organization": "GreenLawAI",
    "email": "aqali.pk92@gmail.com",
    "domains": ["localhost", "*.ngrok-free.dev"],
    "never_expires": False
}

response = requests.post(
    "https://data-api.globalforestwatch.org/auth/apikey",
    json=data,
    headers=headers
)

print(f"Status Code: {response.status_code}")

if response.status_code == 201:
    result = response.json()
    print("\n✅ API KEY CREATED!")
    print(json.dumps(result, indent=2))
    
    # The API key might also be inside 'data'
    api_key = None
    if 'data' in result and 'api_key' in result['data']:
        api_key = result['data']['api_key']
    elif 'api_key' in result:
        api_key = result['api_key']
    
    if api_key:
        print("\n" + "=" * 60)
        print("🔑 YOUR GFW API KEY:")
        print(api_key)
        print("=" * 60)
        
        # Save to file
        with open("gfw_api_key.txt", "w") as f:
            f.write(api_key)
        
        print("\n💾 Key saved to: gfw_api_key.txt")
        print("\n📝 Add this to your .env file:")
        print(f"GFW_API_KEY={api_key}")
        
    else:
        print("\n❌ Could not extract API key from response")
        
elif response.status_code == 400:
    print("\n⚠️ Bad request. The key might already exist for this user.")
    print("Try listing your existing keys:")
    
    # List existing keys
    list_response = requests.get(
        "https://data-api.globalforestwatch.org/auth/apikeys",
        headers=headers
    )
    if list_response.status_code == 200:
        print("\n📋 Your existing API keys:")
        print(json.dumps(list_response.json(), indent=2))
    
else:
    print(f"\n❌ Failed: {response.status_code}")
    print(response.text)