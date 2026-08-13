"""
Cloud Storage Manager
Handles path consistency and artifact management across Colab and local environments.
"""

import os
import json
from pathlib import Path
from typing import Dict, Optional, Literal
from dataclasses import dataclass


@dataclass
class CloudPaths:
    """Centralized path definitions for all artifacts."""
    base: str
    chroma_db: str
    entity_registry: str
    chunks_export: str
    neo4j_imports: str
    models: str
    cache: str
    
    @classmethod
    def from_base(cls, base_path: str) -> 'CloudPaths':
        """Generate all paths from base directory."""
        base = Path(base_path)
        return cls(
            base=str(base),
            chroma_db=str(base / "chroma_db_v3"),
            entity_registry=str(base / "entity_registry.json"),
            chunks_export=str(base / "chunks_export.json"),
            neo4j_imports=str(base / "neo4j_imports"),
            models=str(base / "models"),
            cache=str(base / "cache")
        )


class CloudStorageManager:
    """
    Manages cloud storage paths and validation.
    Ensures consistency between Colab and local environments.
    """
    
    SUPPORTED_PROVIDERS = ["gdrive", "onedrive", "huggingface"]
    
    def __init__(
        self,
        provider: Literal["gdrive", "onedrive", "huggingface"] = "gdrive",
        mount_point: Optional[str] = None,
        auto_detect: bool = True
    ):
        """
        Initialize cloud storage manager.
        
        Args:
            provider: Cloud storage provider
            mount_point: Base path to cloud storage
            auto_detect: Auto-detect environment (Colab vs local)
        """
        if provider not in self.SUPPORTED_PROVIDERS:
            raise ValueError(f"Provider must be one of {self.SUPPORTED_PROVIDERS}")
        
        self.provider = provider
        self.is_colab = self._detect_colab() if auto_detect else False
        
        # Set mount point based on environment
        if mount_point:
            self.mount_point = mount_point
        else:
            self.mount_point = self._get_default_mount_point()
        
        # Generate all artifact paths
        self.paths = CloudPaths.from_base(os.path.join(self.mount_point, "GL_AI"))
        
        print(f"[OK] Cloud Storage: {provider}")
        print(f"[OK] Environment: {'Colab' if self.is_colab else 'Local'}")
        print(f"[OK] Mount Point: {self.mount_point}")
    
    def _detect_colab(self) -> bool:
        """Detect if running in Google Colab."""
        try:
            import google.colab
            return True
        except ImportError:
            return False
    
    def _get_default_mount_point(self) -> str:
        """Get default mount point based on environment and provider."""
        if self.is_colab:
            # Colab defaults
            if self.provider == "gdrive":
                return "/content/drive/MyDrive"
            elif self.provider == "onedrive":
                return "/content/onedrive"
            else:  # huggingface
                return "/content/hf"
        else:
            # Local defaults (Windows)
            if self.provider == "gdrive":
                # Try common Google Drive paths
                for path in ["G:/My Drive", "G:/MyDrive", "C:/Users/*/Google Drive"]:
                    if os.path.exists(path.replace("*", os.getenv("USERNAME", ""))):
                        return path.replace("*", os.getenv("USERNAME", ""))
                return "G:/My Drive"  # Default
            elif self.provider == "onedrive":
                # Try OneDrive path
                username = os.getenv("USERNAME", "")
                return f"C:/Users/{username}/OneDrive"
            else:  # huggingface
                return "./hf_cache"
    
    def mount(self):
        """Mount cloud storage (Colab only)."""
        if not self.is_colab:
            print("[!] Mount not needed on local machine")
            return
        
        if self.provider == "gdrive":
            from google.colab import drive
            drive.mount('/content/drive')
            print("[OK] Google Drive mounted")
        elif self.provider == "onedrive":
            # OneDrive mounting in Colab requires rclone
            print("[!] OneDrive requires manual rclone setup in Colab")
        else:
            print("[!] HuggingFace uses direct API, no mount needed")
    
    def get_path(self, artifact: str) -> str:
        """
        Get path for a specific artifact.
        
        Args:
            artifact: One of: chroma_db, entity_registry, chunks_export, 
                     neo4j_imports, models, cache
        
        Returns:
            Absolute path to artifact
        """
        if not hasattr(self.paths, artifact):
            raise ValueError(f"Unknown artifact: {artifact}")
        return getattr(self.paths, artifact)
    
    def validate_artifacts(self, required: Optional[list] = None) -> Dict[str, bool]:
        """
        Check if required artifacts exist.
        
        Args:
            required: List of required artifacts. If None, checks all.
        
        Returns:
            Dict mapping artifact name to existence status
        """
        if required is None:
            required = ["chroma_db", "entity_registry", "chunks_export"]
        
        validation = {}
        for artifact in required:
            path = self.get_path(artifact)
            
            # For directories, check if they exist and are non-empty
            if artifact in ["chroma_db", "neo4j_imports", "models", "cache"]:
                exists = os.path.isdir(path) and len(os.listdir(path)) > 0
            else:
                # For files
                exists = os.path.isfile(path)
            
            validation[artifact] = exists
        
        return validation
    
    def ensure_directories(self):
        """Create all required directories if they don't exist."""
        dirs = [
            self.paths.base,
            self.paths.chroma_db,
            self.paths.neo4j_imports,
            self.paths.models,
            self.paths.cache
        ]
        
        for dir_path in dirs:
            os.makedirs(dir_path, exist_ok=True)
        
        print(f"[OK] Ensured {len(dirs)} directories exist")
    
    def get_config_dict(self) -> Dict:
        """
        Get configuration dictionary for saving to YAML.
        
        Returns:
            Dict with all paths and settings
        """
        return {
            "provider": self.provider,
            "mount_point": self.mount_point,
            "is_colab": self.is_colab,
            "paths": {
                "base": self.paths.base,
                "chroma_db": self.paths.chroma_db,
                "entity_registry": self.paths.entity_registry,
                "chunks_export": self.paths.chunks_export,
                "neo4j_imports": self.paths.neo4j_imports,
                "models": self.paths.models,
                "cache": self.paths.cache
            }
        }
    
    def save_config(self, output_path: str = "config/cloud_paths.json"):
        """Save current configuration to JSON file."""
        config = self.get_config_dict()
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        print(f"[OK] Saved cloud config to {output_path}")
    
    @classmethod
    def from_config(cls, config_path: str = "config/cloud_paths.json") -> 'CloudStorageManager':
        """Load configuration from JSON file."""
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        return cls(
            provider=config['provider'],
            mount_point=config['mount_point'],
            auto_detect=False
        )
    
    def print_validation_report(self):
        """Print a detailed validation report."""
        print("\n" + "="*60)
        print("CLOUD STORAGE VALIDATION")
        print("="*60)
        
        validation = self.validate_artifacts()
        
        all_valid = all(validation.values())
        
        for artifact, exists in validation.items():
            status = "[OK]" if exists else "[ERR]"
            path = self.get_path(artifact)
            print(f"{status} {artifact:20s} → {path}")
        
        print("="*60)
        
        if all_valid:
            print("✅ All required artifacts found")
        else:
            print("[!] Missing artifacts detected")
            print("Run Colab ingestion pipeline to generate missing files")
        
        return all_valid


if __name__ == "__main__":
    # Test
    cloud = CloudStorageManager(provider="gdrive")
    cloud.ensure_directories()
    cloud.print_validation_report()
    cloud.save_config()
