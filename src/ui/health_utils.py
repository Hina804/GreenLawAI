import os
import requests
import logging
import urllib3
from dotenv import load_dotenv

# Suppress SSL warnings for self-signed or ngrok certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logger = logging.getLogger(__name__)

def check_llm_health():
    """
    Check if LLM is accessible - Reinforced with retries and SSL ignore.
    """
    try:
        load_dotenv()
        url = os.getenv("COLAB_URL")
        if not url:
            return False
            
        full_url = f"{url.rstrip('/')}/health"
        headers = {"ngrok-skip-browser-warning": "any"}
        
        # 3-Attempt Retry Logic for network stability
        for attempt in range(3):
            try:
                # verify=False handles ngrok/colab SSL issues
                response = requests.get(full_url, headers=headers, timeout=8, verify=False)
                if response.status_code == 200:
                    return True
            except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError):
                if attempt < 2: 
                    import time
                    time.sleep(1)
                    continue
        return False
    except Exception as e:
        logger.warning(f"Health check exception: {e}")
        return False
