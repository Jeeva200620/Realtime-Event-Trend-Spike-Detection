import time
import uuid
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class RawEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = Field(default_factory=time.time)
    track: str  # "organic" or "institutional"
    source: str # e.g., "Bluesky", "SEC EDGAR", "BSE India"
    text: str
    author: Optional[str] = "Anonymous"
    url: Optional[str] = None
    region: str = "Global" # "India", "USA", "Global"
    matched_tokens: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class BaseStreamConsumer:
    """Base interface for all async stream listeners."""
    def __init__(self, name: str, track: str):
        self.name = name
        self.track = track
        self.is_running = False

    async def start(self, event_queue):
        raise NotImplementedError

    async def stop(self):
        self.is_running = False
