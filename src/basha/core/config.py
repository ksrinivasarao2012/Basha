import os
import yaml
from pathlib import Path
from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv()

class Settings:
    """
    Handles loading of main application configuration and backend parameters
    from YAML files and environment variables.
    """
    def __init__(self):
        # Locate project root (assuming this file is at src/basha/core/config.py)
        root = Path(__file__).parent.parent.parent.parent
        config_path = root / "config" / "config.yaml"
        backends_path = root / "config" / "backends.yaml"
        
        # Default fallback values
        self.default_backend = "gtts"
        self.translation_backend = "deep_translator"
        self.cache_enabled = True
        self.cache_max_size_mb = 512
        self.chunking_max_chars = 240
        self.eval_cer_threshold = 0.15
        
        self.backends = {}
        
        # 1. Load config.yaml
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
                self.default_backend = config.get("default_backend", self.default_backend)
                self.translation_backend = config.get("translation_backend", self.translation_backend)
                
                cache_cfg = config.get("cache", {})
                self.cache_enabled = cache_cfg.get("enabled", self.cache_enabled)
                self.cache_max_size_mb = cache_cfg.get("max_size_mb", self.cache_max_size_mb)
                
                chunk_cfg = config.get("chunking", {})
                self.chunking_max_chars = chunk_cfg.get("max_chars", self.chunking_max_chars)
                
                eval_cfg = config.get("eval", {})
                self.eval_cer_threshold = eval_cfg.get("cer_threshold", self.eval_cer_threshold)
                
        # 2. Load backends.yaml
        if backends_path.exists():
            with open(backends_path, "r", encoding="utf-8") as f:
                self.backends = yaml.safe_load(f) or {}
                
        # 3. Read secrets/tokens from Environment
        self.sarvam_api_key = os.getenv("SARVAM_API_KEY", "")
        self.hf_token = os.getenv("HF_TOKEN", "")

# Global shared settings instance
settings = Settings()
