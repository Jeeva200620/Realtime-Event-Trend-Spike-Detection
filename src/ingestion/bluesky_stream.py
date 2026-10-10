import json
import asyncio
import logging
import aiohttp
import feedparser
import websockets
from typing import Set, List
from src.config import settings
from src.security.sanitizer import SecuritySanitizer
from src.ingestion.base_stream import BaseStreamConsumer, RawEvent

logger = logging.getLogger("OrganicStream")

JETSTREAM_URLS = [
    "wss://jetstream1.us-east.bsky.network/subscribe?wantedCollections=app.bsky.feed.post",
    "wss://jetstream2.us-east.bsky.network/subscribe?wantedCollections=app.bsky.feed.post",
    "wss://jetstream1.us-west.bsky.network/subscribe?wantedCollections=app.bsky.feed.post",
    "wss://jetstream2.us-west.bsky.network/subscribe?wantedCollections=app.bsky.feed.post",
]

# Supplementary real-time news RSS feeds for continuous high-availability
ORGANIC_WIRE_FEEDS = [
    {
        "name": "India Breaking Citizen Wire",
        "url": "https://news.google.com/rss/headlines/section/topic/NATION?hl=en-IN&gl=IN&ceid=IN:en",
        "region": "India",
        "interval": 20
    },
    {
        "name": "US Breaking Citizen Wire",
        "url": "https://news.google.com/rss/headlines/section/topic/NATION?hl=en-US&gl=US&ceid=US:en",
        "region": "USA",
        "interval": 20
    },
    {
        "name": "Global Emergency & Seismic Wire",
        "url": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.atom",
        "region": "Global",
        "interval": 25
    }
]

class BlueskyStreamConsumer(BaseStreamConsumer):
    def __init__(self):
        super().__init__(name="Organic & Eyewitness Feeds", track="organic")
        self.shock_tokens = set(t.lower() for t in settings.SHOCK_TOKENS)
        self.geo_india = set(t.lower() for t in settings.GEO_INDIA)
        self.geo_usa = set(t.lower() for t in settings.GEO_USA)
        self.seen_guids: Set[str] = set()

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

    async def _poll_supplementary_wires(self, event_queue: asyncio.Queue):
        """Continuously pulls breaking news so the radar never freezes even if websocket disconnects"""
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"}
        connector = aiohttp.TCPConnector(ssl=False)
        
        async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
            while self.is_running:
                for feed in ORGANIC_WIRE_FEEDS:
                    try:
                        async with session.get(feed["url"], timeout=10) as resp:
                            if resp.status == 200:
                                text = await resp.text()
                                parsed = feedparser.parse(text)
                                for entry in parsed.entries[:6]:
                                    guid = entry.get("id") or entry.get("link") or entry.get("title")
                                    if not guid or guid in self.seen_guids:
                                        continue
                                    self.seen_guids.add(guid)
                                    if len(self.seen_guids) > 4000:
                                        self.seen_guids.pop()

                                    title = entry.get("title", "")
                                    text_lower = title.lower()
                                    matched, reg = self.extract_matches(text_lower)
                                    
                                    # If seismic feed or shock match
                                    if "usgs" in feed["url"]:
                                        matched = ["earthquake"]
                                        reg = "Global"
                                    
                                    if matched or any(g in text_lower for g in self.geo_india) or any(g in text_lower for g in self.geo_usa):
                                        sanitized = SecuritySanitizer.clean_text(title)
                                        event = RawEvent(
                                            track="organic",
                                            source=feed["name"],
                                            text=sanitized,
                                            author=feed["name"],
                                            url=entry.get("link"),
                                            region=feed["region"] if feed["region"] != "Global" else reg,
                                            matched_tokens=matched if matched else ["breaking news"],
                                            metadata={"feed_title": title}
                                        )
                                        await event_queue.put(event)
                    except Exception as e:
                        logger.debug(f"Wire poll note: {e}")
                await asyncio.sleep(15)

    async def start(self, event_queue: asyncio.Queue):
        self.is_running = True
        url_idx = 0
        backoff = 2

        logger.info("Starting Organic & Eyewitness stream listeners...")
        
        # Start supplementary high-availability news poller in parallel
        asyncio.create_task(self._poll_supplementary_wires(event_queue))

        while self.is_running:
            url = JETSTREAM_URLS[url_idx % len(JETSTREAM_URLS)]
            try:
                async with websockets.connect(url, ping_interval=15, ping_timeout=10) as ws:
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
                            
            except (websockets.exceptions.ConnectionClosedError, OSError, Exception) as e:
                logger.warning(f"Bluesky stream connection note ({e}). Rotating endpoint in {backoff}s...")
                url_idx += 1
                await asyncio.sleep(backoff)
                backoff = min(backoff * 1.5, 6) # Max 6s backoff for instant recovery
