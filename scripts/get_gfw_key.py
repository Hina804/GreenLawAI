import requests
import getpass
import json

def get_gfw_api_key():
    print("--- Global Forest Watch API Key Generator ---")
    email = "alihinaali2022@gmail.com"
    print(f"Using email: {email}")
    
    print("\n[NOTE] As you type your password, characters will be INVISIBLE for security. Just type it and press Enter.")
    password = getpass.getpass("Enter your MyGFW Password: ")
    
    auth_url = "https://data-api.globalforestwatch.org/auth/token"
    
    # 1. Get Access Token
    try:
        print("\n[1/2] Authenticating with GFW...")
        response = requests.post(
            auth_url, 
            json={"username": email, "password": password},
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code != 200:
            print(f"❌ Authentication failed: {response.text}")
            return
            
        token = response.json().get("data", {}).get("access_token")
        if not token:
            print("❌ Token not found in response.")
            return
            
        print("✅ Authentication successful!")
        
        # 2. Create API Key
        print("[2/2] Requesting API Key...")
        apikey_url = "https://data-api.globalforestwatch.org/auth/apikey"
        
        payload = {
            "alias": "GreenLawAI-FYP",
            "email": email,
            "organization": "Project GreenLawAI",
            "domains": ["localhost"]
        }
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        key_response = requests.post(apikey_url, json=payload, headers=headers)
        
        if key_response.status_code == 200 or key_response.status_code == 201:
            data = key_response.json().get("data", {})
            api_key = data.get("api_key")
            print("\n" + "="*50)
            print("🚀 SUCCESS! YOUR GFW API KEY IS:")
            print(api_key)
            print("="*50)
            print("\nSave this key! You will need to provide it to the GreenLawAI system.")
        else:
            print(f"❌ Failed to create API key: {key_response.text}")
            
    except Exception as e:
        print(f"❌ An error occurred: {e}")

if __name__ == "__main__":
    get_gfw_api_key()
