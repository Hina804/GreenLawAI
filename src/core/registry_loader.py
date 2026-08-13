import importlib
from typing import Any, Dict, Type, Optional
from loguru import logger

from core.contracts import BasePipelineComponent

class ModuleLoader:
    """
    Phase 3 & 3.5: Secure Dynamic Module Loader.
    Enforces isolation, interface compliance, and runtime safety.
    """

    @staticmethod
    def instantiate(module_path: str, class_name: str, **kwargs) -> Optional[Any]:
        """
        Dynamically imports a class and instantiates it.
        Phase 3.5: Added strict inheritance, existence, and safety checks.
        """
        try:
            # 1. Module Path Validation
            try:
                module = importlib.import_module(module_path)
            except ImportError as e:
                logger.error(f"[REGISTRY] Module not found: {module_path} | {e}")
                return None

            # 2. Class Existence Validation
            if not hasattr(module, class_name):
                logger.error(f"[REGISTRY] Class '{class_name}' not found in module '{module_path}'")
                return None

            cls = getattr(module, class_name)

            # 3. Inheritance Validation (Phase 3.5 Hardening)
            if not issubclass(cls, BasePipelineComponent):
                logger.error(f"[CONTRACT] Class '{class_name}' must inherit from BasePipelineComponent")
                return None

            # 4. Safe Instantiation
            instance = cls(**kwargs)
            logger.info(f"[REGISTRY] Successfully loaded and validated: {module_path}.{class_name}")
            return instance

        except Exception as e:
            logger.error(f"[REGISTRY] Fatal instantiation error: {module_path}.{class_name} | {e}")
            return None
