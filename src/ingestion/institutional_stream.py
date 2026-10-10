import asyncio
import logging
import aiohttp
import feedparser
from typing import Set, Dict, List
from src.config import settings
from src.security.sanitizer import SecuritySanitizer
from src.ingestion.base_stream import BaseStreamConsumer, RawEvent

logger = logging.getLogger("InstitutionalStream")

INSTITUTIONAL_FEEDS = [
    {
        "name": "SEC EDGAR Latest Filings (US)",
        "url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=&company=&dateb=&owner=include&start=0&count=30&output=atom",
        "region": "USA",
        "poll_interval": 30,
        "is_sec": True
    },
    {
        "name": "SEBI Regulatory Orders (India)",
        "url": "https://www.sebi.gov.in/sebirss.xml",
        "region": "India",
        "poll_interval": 60,
        "is_sec": False
    },
    {
        "name": "RBI Press Releases (India)",
        "url": "https://rbi.org.in/pressreleases_rss.xml",
        "region": "India",
        "poll_interval": 60,
        "is_sec": False
    },
    {
        "name": "US DOJ Antitrust & Regulatory News",
        "url": "https://www.justice.gov/feeds/press-releases.xml",
        "region": "USA",
        "poll_interval": 90,
        "is_sec": False
    },
    {
        "name": "India Financial Breaking Wire",
        "url": "https://www.moneycontrol.com/rss/MCtopnews.xml",
        "region": "India",
        "poll_interval": 45,
        "is_sec": False
    }
]

class InstitutionalStreamConsumer(BaseStreamConsumer):
    def __init__(self):
        super().__init__(name="Institutional Wires & Regulatory Feeds", track="institutional")
        self.seen_guids: Set[str] = set()
        self.institutional_tokens = set(t.lower() for t in settings.INSTITUTIONAL_TOKENS)
        self.headers = {
            "User-Agent": f"EarlyWarningRadar/1.0 ({settings.USER_AGENT_EMAIL})",
            "Accept": "application/atom+xml, application/rss+xml, application/xml, text/xml"
        }

    def match_tokens(self, text_lower: str) -> List[str]:
        matched = []
        for token in self.institutional_tokens:
            if token in text_lower:
                matched.append(token)
        return matched

    async def poll_feed(self, session: aiohttp.ClientSession, feed_info: dict, event_queue: asyncio.Queue):
        url = feed_info["url"]
        name = feed_info["name"]
        region = feed_info["region"]

        try:
            async with session.get(url, headers=self.headers, timeout=15) as resp:
                if resp.status != 200:
                    return
                content = await resp.text()
                parsed = feedparser.parse(content)

                for entry in parsed.entries[:15]:
                    guid = entry.get("id") or entry.get("link") or entry.get("title")
                    if not guid or guid in self.seen_guids:
                        continue
                    
                    self.seen_guids.add(guid)
                    # Keep seen set bounded
                    if len(self.seen_guids) > 5000:
                        self.seen_guids.pop()

                    title = entry.get("title", "")
                    summary = entry.get("summary", "")
                    full_text = f"{title}. {summary}"
                    text_lower = full_text.lower()

                    matched = self.match_tokens(text_lower)
                    
                    # For SEC EDGAR or direct regulatory orders, even 8-K filings or orders are high priority
                    if matched or feed_info.get("is_sec", False):
                        if not matched and "8-k" in text_lower:
                            matched = ["8-k major event filing"]
                        
                        sanitized = SecuritySanitizer.clean_text(full_text)
                        link = entry.get("link")

                        event = RawEvent(
                            track="institutional",
                            source=name,
                            text=sanitized,
                            author=name,
                            url=link,
                            region=region,
                            matched_tokens=matched if matched else ["regulatory filing"],
                            metadata={"feed_title": title}
                        )
                        await event_queue.put(event)
                        logger.info(f"[Institutional] Detected filing from {name}: {title[:60]}")
        except Exception as e:
            logger.debug(f"Feed poll failed for {name}: {e}")

    async def start(self, event_queue: asyncio.Queue):
        self.is_running = True
        logger.info("Starting Institutional & Regulatory Poller...")

        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            while self.is_running:
                tasks = [
                    self.poll_feed(session, feed_info, event_queue)
                    for feed_info in INSTITUTIONAL_FEEDS
                ]
                await asyncio.gather(*tasks, return_exceptions=True)
                # Global cycle pause
                await asyncio.sleep(25)
