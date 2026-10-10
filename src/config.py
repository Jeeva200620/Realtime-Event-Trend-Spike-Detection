import os
import yaml
from pathlib import Path
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load .env file
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"

def load_yaml_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}

yaml_cfg = load_yaml_config()

class AppSettings(BaseModel):
    # Server
    HOST: str = os.getenv("HOST", "127.0.0.1")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    # Regions & Detection
    REGIONS: list[str] = [r.strip() for r in os.getenv("REGIONS", "India,USA").split(",")]
    SENSITIVITY_THRESHOLD: float = float(os.getenv("SENSITIVITY_THRESHOLD", "3.5"))
    USER_AGENT_EMAIL: str = os.getenv("USER_AGENT_EMAIL", "analyst@earlywarning.local")
    
    # AI Keys
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    USE_LOCAL_OLLAMA: bool = os.getenv("USE_LOCAL_OLLAMA", "false").lower() == "true"
    OLLAMA_ENDPOINT: str = os.getenv("OLLAMA_ENDPOINT", "http://localhost:11434")
    
    # Alerting (Optional)
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")
    DISCORD_WEBHOOK_URL: str = os.getenv("DISCORD_WEBHOOK_URL", "")

    # Config YAML maps
    MICRO_WINDOW_SECONDS: int = yaml_cfg.get("detection", {}).get("micro_window_seconds", 60)
    MACRO_WINDOW_SECONDS: int = yaml_cfg.get("detection", {}).get("macro_window_seconds", 300)
    MIN_VOLUME_THRESHOLD: int = yaml_cfg.get("detection", {}).get("min_volume_threshold", 4)
    COOLDOWN_SECONDS: int = yaml_cfg.get("detection", {}).get("cooldown_seconds", 180)
    
    SHOCK_TOKENS: list[str] = yaml_cfg.get("keywords", {}).get("shock_tokens", [])
    INSTITUTIONAL_TOKENS: list[str] = yaml_cfg.get("keywords", {}).get("institutional_tokens", [])
    GEO_INDIA: list[str] = yaml_cfg.get("keywords", {}).get("geo_india", [])
    GEO_USA: list[str] = yaml_cfg.get("keywords", {}).get("geo_usa", [])

settings = AppSettings()
