import socket
import os
import sys
import yaml
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

def check_port(host, port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(2)
        try:
            s.connect((host, port))
            return True
        except:
            return False

def main():
    print("="*60)
    print("       🌲 GreenLawAI Infrastructure Diagnostic 🌲")
    print("="*60)
    
    # 1. Configuration Check
    config_path = Path("config/rag_config.yaml")
    print(f"\n[1] Configuration Check:")
    if config_path.exists():
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        print(f"  ✓ Found {config_path}")
    else:
        print(f"  ❌ MISSING {config_path}")
        config = {}

    # 2. Neo4j Check
    print(f"\n[2] Neo4j Status:")
    neo4j_uri = config.get('neo4j', {}).get('uri', 'bolt://localhost:7687')
    host = "localhost"
    port = 7687
    if "://" in neo4j_uri:
        parts = neo4j_uri.split("://")[1].split(":")
        host = parts[0]
        port = int(parts[1]) if len(parts) > 1 else 7687

    bolt_open = check_port(host, port)
    http_open = check_port(host, 7474)

    if bolt_open:
        print(f"  ✓ Bolt Port {port} is OPEN")
    else:
        print(f"  ❌ Bolt Port {port} is CLOSED")
        print(f"     Hint: Neo4j database is NOT running.")
        print(f"     Action: Start Neo4j Desktop or run 'docker-compose up -d'")

    if http_open:
        print(f"  ✓ Browser Port 7474 is OPEN (http://{host}:7474)")
    else:
        print(f"  ⚠ Browser Port 7474 is CLOSED")

    try:
        import neo4j
        print(f"  ✓ Python package 'neo4j' is installed")
    except ImportError:
        print(f"  ❌ Python package 'neo4j' is MISSING")
        print(f"     Action: pip install neo4j")

    # 3. FAISS Check
    print(f"\n[3] FAISS Vector Store:")
    faiss_dir = Path("faiss_index")
    if faiss_dir.exists():
        print(f"  ✓ Found {faiss_dir}")
    else:
        print(f"  ❌ MISSING {faiss_dir}")
        print(f"     Action: Run ingestion pipeline to build vector index.")

    # 4. LLM Provider Check
    print(f"\n[4] LLM Provider:")
    provider = config.get('llm', {}).get('provider', 'openai')
    print(f"  Mode: {provider}")
    if provider == "colab":
        url = config.get('llm', {}).get('colab_url', '')
        print(f"  URL: {url}")
        if url:
            print("  ✓ Colab URL configured")
        else:
            print("  ❌ Colab URL missing from .env or rag_config.yaml")

    print("\n" + "="*60)
    print("Diagnostic Complete.")
    if not bolt_open:
        print("\nCRITICAL: GraphRAG will be disabled until Neo4j is started.")
    print("="*60)

if __name__ == "__main__":
    main()
