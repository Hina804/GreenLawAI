import os
from pathlib import Path
try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseSettings

class Settings(BaseSettings):
    # Base Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    DATA_RAW_DIR: Path = BASE_DIR / "data_raw"
    DATA_PROCESSED_DIR: Path = BASE_DIR / "data_processed"
    OUTPUTS_DIR: Path = BASE_DIR / "outputs"
    SRC_DIR: Path = BASE_DIR / "src"
    
    # App Config
    APP_NAME: str = "GreenLawAI"
    VERSION: str = "0.1.0"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    # LLM Settings
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "openai")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    COLAB_URL: str = os.getenv("COLAB_URL", "")
    
    # DB Settings
    NEO4J_URI: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER: str = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "password")
    CHROMA_PERSIST_DIR: str = os.getenv("CHROMA_PERSIST_DIR", "./faiss_index")

    # External APIs (Audit Fix)
    NASA_FIRMS_TOKEN: str = os.getenv("NASA_FIRMS_TOKEN", "")
    OPENWEATHERMAP_KEY: str = os.getenv("OPENWEATHERMAP_KEY", "")

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"

settings = Settings()
