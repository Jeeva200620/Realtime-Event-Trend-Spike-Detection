import os
import json
import asyncio
import logging
from pathlib import Path
from typing import List, Set
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

from src.config import settings
from src.ingestion.base_stream import RawEvent
from src.ingestion.bluesky_stream import BlueskyStreamConsumer
from src.ingestion.institutional_stream import InstitutionalStreamConsumer
from src.detection.spike_detector import SlidingWindowSpikeDetector
from src.verification.verifier import EventVerifier, VerifiedAlert
from src.simulation.test_simulator import SIMULATION_SCENARIOS, inject_scenario

logger = logging.getLogger("RadarServer")

app = FastAPI(title="Early-Warning Event & Trend Spike Detection Radar")

# Global event queue & state
event_queue: asyncio.Queue = asyncio.Queue()
detector = SlidingWindowSpikeDetector()
verifier = EventVerifier()

# Global memory caches
verified_alerts: List[VerifiedAlert] = []
recent_events_cache: List[dict] = []
active_websockets: Set[WebSocket] = set()

# Background consumer tasks
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
app.mount("/static", StaticFiles(directory=str(ROOT_DIR)), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    index_file = ROOT_DIR / "index.html"
    return FileResponse(index_file)

@app.get("/styles.css")
async def serve_styles():
    return FileResponse(ROOT_DIR / "styles.css")

@app.get("/app.js")
async def serve_script():
    return FileResponse(ROOT_DIR / "app.js")

@app.get("/api/status")
async def get_status():
    return {
        "status": "online",
        "regions": settings.REGIONS,
        "total_ingested": detector.total_ingested,
        "posts_per_second": detector.posts_per_second,
        "active_alerts_count": len(verified_alerts),
        "sensitivity_z_threshold": detector.z_threshold,
        "ai_verifier_enabled": bool(settings.GEMINI_API_KEY and len(settings.GEMINI_API_KEY.strip()) > 5),
    }

@app.get("/api/alerts")
async def get_alerts():
    return [alert.model_dump() for alert in reversed(verified_alerts)]

@app.get("/api/events/recent")
async def get_recent_events():
    return list(reversed(recent_events_cache[-60:]))

@app.post("/api/simulate/{scenario_key}")
async def trigger_simulation(scenario_key: str):
    if scenario_key not in SIMULATION_SCENARIOS:
        raise HTTPException(status_code=404, detail="Scenario not found")
    
    count = await inject_scenario(scenario_key, event_queue)
    return {"status": "injected", "scenario": scenario_key, "posts_count": count}

@app.get("/api/scenarios")
async def list_scenarios():
    return {
        k: {"title": v["title"], "track": v["track"], "region": v["region"], "token": v["burst_token"]}
        for k, v in SIMULATION_SCENARIOS.items()
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_websockets.add(websocket)
    try:
        # Send initial state snapshot
        await websocket.send_json({
            "type": "init",
            "status": "connected",
            "alerts": [a.model_dump() for a in reversed(verified_alerts[-15:])],
            "recent_events": list(reversed(recent_events_cache[-30:])),
            "stats": {
                "total_ingested": detector.total_ingested,
                "posts_per_second": detector.posts_per_second,
                "active_alerts": len(verified_alerts),
            }
        })
        while True:
            # Keepalive receiver
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except (WebSocketDisconnect, ConnectionResetError, OSError):
        active_websockets.discard(websocket)
    except Exception:
        active_websockets.discard(websocket)

async def broadcast_ws(payload: dict):
    if not active_websockets:
        return
    dead = set()
    for ws in list(active_websockets):
        try:
            await ws.send_json(payload)
        except Exception:
            dead.add(ws)
    for ws in dead:
        active_websockets.discard(ws)

async def event_processing_loop():
    """Consumes raw events, feeds spike detector, runs evaluation, and broadcasts"""
    logger.info("Event Processing Loop started.")
    last_eval_time = 0.0

    while True:
        try:
            # Drain up to 50 events from queue
            batch = []
            while not event_queue.empty() and len(batch) < 50:
                batch.append(event_queue.get_nowait())

            for event in batch:
                detector.record_event(event)
                ev_dict = event.model_dump()
                recent_events_cache.append(ev_dict)
                if len(recent_events_cache) > 200:
                    recent_events_cache.pop(0)

                # Broadcast raw event to live dashboard stream
                await broadcast_ws({
                    "type": "new_event",
                    "event": ev_dict
                })

            now = asyncio.get_event_loop().time()
            # Run spike evaluation every 1.5 seconds
            if now - last_eval_time >= 1.5:
                last_eval_time = now
                spikes = detector.evaluate_spikes()
                for spike in spikes:
                    alert = await verifier.verify_spike(spike)
                    if alert:
                        verified_alerts.append(alert)
                        if len(verified_alerts) > 100:
                            verified_alerts.pop(0)
                        
                        logger.warning(f"[ALERT BROADCAST] {alert.headline}")
                        await broadcast_ws({
                            "type": "spike_alert",
                            "alert": alert.model_dump()
                        })

                # Broadcast telemetry update
                await broadcast_ws({
                    "type": "telemetry",
                    "stats": {
                        "total_ingested": detector.total_ingested,
                        "posts_per_second": detector.posts_per_second,
                        "active_alerts": len(verified_alerts),
                        "tracked_tokens": len(detector.token_history)
                    }
                })

            await asyncio.sleep(0.3)
        except Exception as e:
            logger.error(f"Error in event processing loop: {e}", exc_info=True)
            await asyncio.sleep(1)

@app.on_event("startup")
async def startup_event():
    logger.info("Initializing Radar Engine background services...")
    
    # 1. Start event processing loop
    asyncio.create_task(event_processing_loop())

    # 2. Start Bluesky Stream
    bsky_consumer = BlueskyStreamConsumer()
    asyncio.create_task(bsky_consumer.start(event_queue))

    # 3. Start Institutional Stream
    inst_consumer = InstitutionalStreamConsumer()
    asyncio.create_task(inst_consumer.start(event_queue))
