"""
Configuration Setup Wizard
Interactive tool to configure cloud storage paths.
"""

import os
import sys
from pathlib import Path
import yaml

def print_header():
    """Print header."""
    print("\n" + "="*70)
    print("  CLOUD STORAGE CONFIGURATION WIZARD")
    print("="*70)

def detect_google_drive():
    """Try to detect Google Drive path on Windows."""
    possible_paths = [
        "G:/My Drive",
        "G:/MyDrive",
        f"C:/Users/{os.getenv('USERNAME', '')}/Google Drive",
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    return None

def detect_onedrive():
    """Try to detect OneDrive path on Windows."""
    username = os.getenv('USERNAME', '')
    possible_paths = [
        f"C:/Users/{username}/OneDrive",
        f"C:/Users/{username}/OneDrive - Personal",
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    return None

def main():
    print_header()
    
    print("\nThis wizard will help you configure cloud storage paths.")
    print("The configuration will be saved to: config/rag_config.yaml")
    
    # Step 1: Choose provider
    print("\n" + "-"*70)
    print("STEP 1: Choose Cloud Storage Provider")
    print("-"*70)
    print("\n1. Google Drive")
    print("2. OneDrive")
    print("3. HuggingFace (advanced)")
    
    while True:
        choice = input("\nEnter choice (1-3): ").strip()
        if choice in ['1', '2', '3']:
            break
        print("Invalid choice. Please enter 1, 2, or 3.")
    
    provider_map = {'1': 'gdrive', '2': 'onedrive', '3': 'huggingface'}
    provider = provider_map[choice]
    
    # Step 2: Find mount point
    print("\n" + "-"*70)
    print("STEP 2: Locate Cloud Storage Path")
    print("-"*70)
    
    detected_path = None
    if provider == 'gdrive':
        detected_path = detect_google_drive()
    elif provider == 'onedrive':
        detected_path = detect_onedrive()
    
    if detected_path:
        print(f"\n✓ Auto-detected path: {detected_path}")
        use_detected = input("Use this path? (y/n): ").strip().lower()
        if use_detected == 'y':
            mount_point = detected_path
        else:
            mount_point = input("Enter your cloud storage path: ").strip()
    else:
        print("\n⚠ Could not auto-detect path.")
        print("\nHow to find your path:")
        if provider == 'gdrive':
            print("1. Open File Explorer")
            print("2. Look for 'Google Drive' in the sidebar")
            print("3. Right-click → Properties → Location")
            print("   Example: G:/My Drive")
        elif provider == 'onedrive':
            print("1. Right-click OneDrive icon in taskbar")
            print("2. Settings → Account")
            print("   Example: C:/Users/YourName/OneDrive")
        
        mount_point = input("\nEnter your cloud storage path: ").strip()
    
    # Verify path exists
    if not os.path.exists(mount_point):
        print(f"\n⚠ WARNING: Path does not exist: {mount_point}")
        create = input("Continue anyway? (y/n): ").strip().lower()
        if create != 'y':
            print("\nSetup cancelled.")
            return
    
    # Step 3: Create GL_AI folder
    print("\n" + "-"*70)
    print("STEP 3: Create GL_AI Folder")
    print("-"*70)
    
    gl_ai_path = os.path.join(mount_point, "GL_AI")
    
    if os.path.exists(gl_ai_path):
        print(f"\n✓ GL_AI folder already exists: {gl_ai_path}")
    else:
        print(f"\nWill create folder: {gl_ai_path}")
        create = input("Create now? (y/n): ").strip().lower()
        if create == 'y':
            try:
                os.makedirs(gl_ai_path, exist_ok=True)
                print(f"✓ Created: {gl_ai_path}")
            except Exception as e:
                print(f"❌ Error creating folder: {e}")
                return
    
    # Step 4: Show what will be created
    print("\n" + "-"*70)
    print("STEP 4: Cloud Storage Structure")
    print("-"*70)
    
    print(f"\nThe following structure will be used:")
    print(f"\n{gl_ai_path}/")
    print(f"├── chroma_db/           (Vector store)")
    print(f"├── entity_registry.json (Entity metadata)")
    print(f"├── chunks_export.json   (Structured chunks)")
    print(f"├── neo4j_imports/       (CSV files)")
    print(f"├── models/              (Cached models)")
    print(f"└── cache/               (Temporary files)")
    
    # Step 5: Update configuration
    print("\n" + "-"*70)
    print("STEP 5: Save Configuration")
    print("-"*70)
    
    config_path = "config/rag_config.yaml"
    
    # Load existing config or create new
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
    else:
        config = {}
    
    # Update cloud storage settings
    if 'cloud_storage' not in config:
        config['cloud_storage'] = {}
    
    config['cloud_storage']['provider'] = provider
    config['cloud_storage']['mount_point'] = mount_point
    
    # Save
    os.makedirs('config', exist_ok=True)
    with open(config_path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    
    print(f"\n✓ Configuration saved to: {config_path}")
    
    # Step 6: Verify
    print("\n" + "-"*70)
    print("STEP 6: Verification")
    print("-"*70)
    
    print("\nTesting configuration...")
    
    try:
        sys.path.insert(0, 'src')
        from rag.cloud_storage import CloudStorageManager
        
        cloud = CloudStorageManager(
            provider=provider,
            mount_point=mount_point
        )
        
        print("\n✓ CloudStorageManager initialized successfully")
        print(f"✓ Provider: {cloud.provider}")
        print(f"✓ Mount Point: {cloud.mount_point}")
        print(f"✓ Base Path: {cloud.paths.base}")
        
        # Create directories
        print("\nCreating required directories...")
        cloud.ensure_directories()
        
        # Validate
        print("\nChecking for artifacts...")
        validation = cloud.validate_artifacts()
        
        all_found = all(validation.values())
        
        for artifact, exists in validation.items():
            status = "✓" if exists else "❌"
            print(f"{status} {artifact}")
        
        if not all_found:
            print("\n⚠ Some artifacts are missing (expected for first-time setup)")
            print("Run the Colab ingestion pipeline to generate them.")
        
        # Save cloud config
        cloud.save_config()
        
    except Exception as e:
        print(f"\n❌ Error during verification: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Done
    print("\n" + "="*70)
    print("  SETUP COMPLETE!")
    print("="*70)
    
    print("\n✅ Configuration saved to: config/rag_config.yaml")
    print("✅ Cloud paths configured")
    
    print("\n📝 Next Steps:")
    print("1. Run Colab ingestion pipeline to generate artifacts")
    print("2. Import data to Neo4j: python scripts/setup_neo4j_from_cloud.py")
    print("3. Start RAG Q&A: python scripts/demo_rag_qa.py")
    
    print("\n" + "="*70)

if __name__ == "__main__":
    main()
