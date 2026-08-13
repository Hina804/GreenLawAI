
import requests
import json
import yaml

def load_config():
    with open("config/rag_config.yaml", "r") as f:
        return yaml.safe_load(f)

def test_connection():
    config = load_config()
    colab_url = config['llm']['colab_url']
    print(f"Testing URL: {colab_url}")

    payload = {
        "context": "The Forest Act 1927 prohibits setting fires in reserved forests.",
        "question": "Can I burn trees?",
        "max_tokens": 100,
        "temperature": 0.1
    }

    try:
        print("Sending request...")
        response = requests.post(f"{colab_url}/generate", json=payload, timeout=30)
        print(f"Status Code: {response.status_code}")
        print("Raw Response Text:")
        print(response.text)
        
        try:
            json_response = response.json()
            print("\nParsed JSON Keys:", list(json_response.keys()))
        except:
            print("Could not parse JSON")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_connection()
