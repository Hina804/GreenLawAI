"""
Update Colab URL
Helper script to quickly update the Colab ngrok URL in the config file.
"""

import sys
import yaml
from pathlib import Path

def update_url(url):
    config_path = Path("config/rag_config.yaml")
    
    # Load config
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Update URL
    if 'llm' not in config:
        config['llm'] = {}
    
    config['llm']['colab_url'] = url
    config['llm']['provider'] = 'colab'
    
    # Save config
    with open(config_path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    
    print(f"✅ Updated Colab URL to: {url}")
    print("You can now run: python scripts/test_colab_connection.py")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/update_colab_url.py <ngrok_url>")
        print("Example: python scripts/update_colab_url.py https://abc1234.ngrok.io")
        sys.exit(1)
    
    url = sys.argv[1]
    update_url(url)
