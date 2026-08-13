import logging
import threading
from typing import Optional

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None

logger = logging.getLogger(__name__)

class ModelRegistry:
    """
    Singleton registry for heavy AI models to prevent redundant loading in parallel agents.
    """
    _instance = None
    _lock = threading.Lock()
    _models = {}

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(ModelRegistry, cls).__new__(cls)
            return cls._instance

    def get_model(self, model_name: str = "all-MiniLM-L6-v2") -> Optional[Any]:
        """Retrieve or load a model singleton."""
        if not SentenceTransformer:
            logger.warning("[ModelRegistry] sentence_transformers not installed.")
            return None

        if model_name not in self._models:
            with self._lock:
                # Double-check inside lock
                if model_name not in self._models:
                    logger.info(f"[ModelRegistry] Loading heavy model: {model_name} on CPU...")
                    try:
                        self._models[model_name] = SentenceTransformer(model_name)
                        logger.info(f"[ModelRegistry] Model {model_name} loaded successfully.")
                    except Exception as e:
                        logger.error(f"[ModelRegistry] Failed to load {model_name}: {e}")
                        return None
        
        return self._models.get(model_name)

# Global access point
model_registry = ModelRegistry()
