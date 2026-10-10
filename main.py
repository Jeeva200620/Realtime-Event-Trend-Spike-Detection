import sys
import logging
import uvicorn
from src.config import settings

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )

def main():
    setup_logging()
    
    ai_status = "Gemini API Configured" if (settings.GEMINI_API_KEY and len(settings.GEMINI_API_KEY.strip()) > 5) else "Mathematical & Pattern Rule Engine ($0 Zero-Key)"
    
    banner = f"""
========================================================================
[ALERT] REAL-TIME EARLY-WARNING EVENT & TREND SPIKE RADAR [IN / US]
========================================================================
* Ingestion Tracks: Track 1 (Organic/Physical) & Track 2 (Institutional)
* Statistical Anomaly: Poisson Sliding-Window Z-Score (Z > {settings.SENSITIVITY_THRESHOLD}sigma)
* Security Guardrails: Strict XML Isolation & Prompt Redactor Active
* AI Verifier: {ai_status}
* Mission Control Dashboard: http://{settings.HOST}:{settings.PORT}
========================================================================
    """
    print(banner)

    uvicorn.run(
        "src.server.app:app",
        host=settings.HOST,
        port=settings.PORT,
        log_level="info",
        reload=False
    )

if __name__ == "__main__":
    main()
