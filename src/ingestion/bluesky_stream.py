import json
import asyncio
import logging
import websockets
from typing import Set
from src.config import settings
from src.security.sanitizer import SecuritySanitizer
from src.ingestion.base_stream import BaseStreamConsumer, RawEvent

logger = logging.getLogger("BlueskyStream")

JETSTREAM_URLS = [
    "wss://jetstream1.us-east.bsky.network/subscribe?wantedCollections=app.bsky.feed.post",
    "wss://jetstream2.us-west.bsky.network/subscribe?wantedCollections=app.bsky.feed.post",
]

class BlueskyStreamConsumer(BaseStreamConsumer):
    def __init__(self):
        super().__init__(name="Bluesky Jetstream", track="organic")
        self.shock_tokens = set(t.lower() for t in settings.SHOCK_TOKENS)
        self.geo_india = set(t.lower() for t in settings.GEO_INDIA)
        self.geo_usa = set(t.lower() for t in settings.GEO_USA)

    def extract_matches(self, text_lower: str):
        matched = []
        for token in self.shock_tokens:
            if token in text_lower:
                matched.append(token)
        
        region = "Global"
        in_match = any(g in text_lower for g in self.geo_india)
        us_match = any(g in text_lower for g in self.geo_usa)
        
        if in_match and not us_match:
            region = "India"
        elif us_match and not in_match:
            region = "USA"
        elif in_match and us_match:
            region = "Both"

        return matched, region

    async def start(self, event_queue: asyncio.Queue):
        self.is_running = True
        url_idx = 0
        backoff = 2

        logger.info("Starting Bluesky Jetstream WebSocket listener...")
        while self.is_running:
            url = JETSTREAM_URLS[url_idx % len(JETSTREAM_URLS)]
            try:
                async with websockets.connect(url, ping_interval=20, ping_timeout=10) as ws:
                    logger.info(f"Connected to Bluesky Jetstream: {url}")
                    backoff = 2
                    
                    while self.is_running:
                        msg = await ws.recv()
                        data = json.loads(msg)
                        
                        commit = data.get("commit", {})
                        if commit.get("collection") != "app.bsky.feed.post":
                            continue
                        
                        record = commit.get("record", {})
                        raw_text = record.get("text", "")
                        if not raw_text:
                            continue
                        
                        text_lower = raw_text.lower()
                        matched_tokens, region = self.extract_matches(text_lower)

                        # If shock token or regional breaking chatter detected
                        if matched_tokens:
                            sanitized = SecuritySanitizer.clean_text(raw_text)
                            author = data.get("did", "bsky_user")
                            rkey = commit.get("rkey", "")
                            post_url = f"https://bsky.app/profile/{author}/post/{rkey}" if rkey else None
                            
                            event = RawEvent(
                                track="organic",
                                source="Bluesky Jetstream",
                                text=sanitized,
                                author=author[:18] + "...",
                                url=post_url,
                                region=region,
                                matched_tokens=matched_tokens,
                                metadata={"langs": record.get("langs", [])}
                            )
                            await event_queue.put(event)
                            
            except (websockets.exceptions.ConnectionClosedError, OSError) as e:
                logger.warning(f"Bluesky stream connection dropped ({e}). Reconnecting in {backoff}s...")
                url_idx += 1
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)
            except Exception as e:
                logger.error(f"Bluesky stream error: {e}", exc_info=False)
                await asyncio.sleep(3)
