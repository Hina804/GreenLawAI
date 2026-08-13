"""
LLM_CLIENT.PY - Ollama Wrapper
"""
import requests
import json
from .config import OLLAMA_BASE_URL, LLM_MODEL

class LLMClient:
    def __init__(self, settings=None, base_url=None, model=None, **kwargs):
        if settings:
            self.base_url = settings.base_url
            self.model = settings.model
        else:
            # Handle parameter mapping from Sanitizer
            self.base_url = base_url or kwargs.get("api_base") or OLLAMA_BASE_URL
            self.model = model or LLM_MODEL
            
        # Store other configuration
        self.config = kwargs
        self.timeout = kwargs.get("timeout", 300)
        self.api_key = kwargs.get("api_key", None)

    def generate(self, prompt, system_prompt=None, **kwargs):
        url = f"{self.base_url}/api/generate"
        model = kwargs.get("model", self.model)
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False
        }
        if system_prompt:
            payload["system"] = system_prompt
        
        # Merge defaults with run-time options
        request_options = self.config.copy()
        if "options" in kwargs:
            request_options.update(kwargs["options"])
            
        # Add top-level params to options if they exist
        for param in ["temperature", "max_tokens", "top_p"]:
            if param in kwargs:
                request_options[param] = kwargs[param]
                
        if request_options:
            payload["options"] = request_options
            
        # Add headers if API key exists
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
            
        try:
            # Set default timeout to 30s if not provided in kwargs
            timeout = kwargs.get("timeout", self.timeout)
            
            # Debug log
            if kwargs.get("debug", False):
                print(f"Sending request to {url} with model {model}...")
                
            response = requests.post(url, json=payload, headers=headers, timeout=timeout)
            response.raise_for_status()
            
            result = response.json().get("response", "")
            if not result and kwargs.get("debug", False):
                print(f"Warning: Empty response from LLM. Status: {response.status_code}")
                
            return result
        except requests.exceptions.Timeout:
            print(f"LLM Error: Request timed out after {timeout}s")
            return ""
        except requests.exceptions.ConnectionError:
            print(f"LLM Error: Could not connect to Ollama at {self.base_url}")
            return ""
        except Exception as e:
            print(f"LLM Error: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Server response: {e.response.text}")
            return ""

