import time
import math
import logging
from collections import defaultdict, deque
from typing import Dict, List, Optional, Tuple, Set
from pydantic import BaseModel, Field
from src.config import settings
from src.ingestion.base_stream import RawEvent

logger = logging.getLogger("SpikeDetector")

class SpikeCandidate(BaseModel):
    id: str
    timestamp: float = Field(default_factory=time.time)
    track: str # "organic" or "institutional"
    region: str # "India", "USA", "Global"
    burst_tokens: List[str]
    z_score: float
    current_velocity: float # mentions in micro window
    baseline_velocity: float # historical mentions per minute
    distinct_sources: List[str]
    sample_texts: List[str]
    primary_source: str
    source_events: List[RawEvent]

class SlidingWindowSpikeDetector:
    def __init__(
        self,
        micro_window: int = settings.MICRO_WINDOW_SECONDS,
        macro_window: int = settings.MACRO_WINDOW_SECONDS,
        min_volume: int = settings.MIN_VOLUME_THRESHOLD,
        z_threshold: float = settings.SENSITIVITY_THRESHOLD,
        cooldown: int = settings.COOLDOWN_SECONDS
    ):
        self.micro_window = micro_window
        self.macro_window = macro_window
        self.min_volume = min_volume
        self.z_threshold = z_threshold
        self.cooldown = cooldown

        # token -> deque of (timestamp, event_id, source, region, text)
        self.token_history: Dict[str, deque] = defaultdict(deque)
        
        # token -> last alert epoch timestamp (for deduplication / cooldown)
        self.last_alert_time: Dict[str, float] = {}
        
        # Recent raw events buffer for cluster context
        self.recent_events: deque[RawEvent] = deque(maxlen=2000)
        
        # Stats tracking for live dashboard
        self.total_ingested = 0
        self.posts_per_second = 0.0
        self._rate_counter = deque(maxlen=60) # timestamps of arrivals

    def record_event(self, event: RawEvent):
        now = time.time()
        self.total_ingested += 1
        self._rate_counter.append(now)
        self.recent_events.append(event)

        tokens = event.matched_tokens
        for token in tokens:
            self.token_history[token].append((now, event))

        # Cleanup arrivals older than 60s for live speedometer
        while self._rate_counter and now - self._rate_counter[0] > 60:
            self._rate_counter.popleft()
        self.posts_per_second = round(len(self._rate_counter) / 60.0, 2)

    def prune_old_entries(self, now: float):
        """Purge timestamps older than macro observation window (e.g. 15 mins)"""
        cutoff = now - 900 # 15 minutes
        for token in list(self.token_history.keys()):
            history = self.token_history[token]
            while history and history[0][0] < cutoff:
                history.popleft()
            if not history:
                del self.token_history[token]

    def evaluate_spikes(self) -> List[SpikeCandidate]:
        now = time.time()
        self.prune_old_entries(now)
        detected_spikes: List[SpikeCandidate] = []

        for token, history in list(self.token_history.items()):
            # 1. Check cooldown
            if now - self.last_alert_time.get(token, 0) < self.cooldown:
                continue

            # 2. Count events in micro window (e.g. last 60s)
            micro_cutoff = now - self.micro_window
            macro_cutoff = now - self.macro_window
            
            micro_events = [ev for (t, ev) in history if t >= micro_cutoff]
            macro_events = [ev for (t, ev) in history if t >= macro_cutoff]

            current_count = len(micro_events)
            
            # Institutional events are lower volume but high significance:
            # allow lower volume threshold for official institutional announcements
            min_req = 1 if any(ev.track == "institutional" for ev in micro_events) else self.min_volume
            
            if current_count < min_req:
                continue

            # 3. Calculate baseline rate (Poisson arrival model)
            # Baseline is arrivals per micro-window duration over macro window
            macro_span_minutes = max((self.macro_window / 60.0), 1.0)
            baseline_per_min = max(len(macro_events) / macro_span_minutes, 0.1)
            expected_in_micro = (baseline_per_min / 60.0) * self.micro_window

            # 4. Modified Poisson Z-Score for burst detection:
            # Z = (Current - Expected) / sqrt(max(Expected, 0.5))
            variance = max(expected_in_micro, 0.5)
            z_score = (current_count - expected_in_micro) / math.sqrt(variance)

            # Institutional orders (e.g. SEBI ban or SEC charge) auto-boost Z-Score
            is_institutional = any(ev.track == "institutional" for ev in micro_events)
            if is_institutional:
                z_score = max(z_score, 4.5)

            if z_score >= self.z_threshold:
                # Group related events
                sources = list(set(ev.source for ev in micro_events))
                regions = [ev.region for ev in micro_events if ev.region != "Global"]
                region = regions[0] if regions else (micro_events[0].region if micro_events else "Global")
                sample_texts = [ev.text for ev in micro_events[-5:]]
                
                track = "institutional" if is_institutional else "organic"
                candidate_id = f"spike_{int(now)}_{token[:10]}"

                spike = SpikeCandidate(
                    id=candidate_id,
                    timestamp=now,
                    track=track,
                    region=region,
                    burst_tokens=[token],
                    z_score=round(float(z_score), 2),
                    current_velocity=float(current_count),
                    baseline_velocity=round(float(baseline_per_min), 2),
                    distinct_sources=sources,
                    sample_texts=sample_texts,
                    primary_source=sources[0] if sources else "Unknown",
                    source_events=micro_events[-10:]
                )

                self.last_alert_time[token] = now
                detected_spikes.append(spike)
                logger.warning(
                    f"[SPIKE DETECTED] Token: '{token}' | Z-Score: {spike.z_score} | "
                    f"Velocity: {current_count} in {self.micro_window}s | Region: {region}"
                )

        return detected_spikes
