"""
Worker server wrapper that runs both the LiveKit worker and a health check HTTP server.
This is required for Cloud Run which expects all containers to listen on an HTTP port.
"""

import asyncio
import logging
import os
import threading
from typing import Dict

from fastapi import FastAPI
import uvicorn

logger = logging.getLogger("worker-server")
logging.basicConfig(level=logging.INFO)

# Create a simple FastAPI app for health checks
app = FastAPI(title="LiveKit Worker Health Check")


@app.get("/health")
async def health() -> Dict[str, str]:
    """Health check endpoint for Cloud Run"""
    return {"status": "ok", "service": "livekit-worker"}


def run_health_server():
    """Run the health check HTTP server in a separate thread"""
    port = int(os.getenv("PORT", "8080"))
    logger.info("Starting health check server on port %d", port)
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")


def run_livekit_worker():
    """Run the LiveKit worker in the main thread"""
    try:
        logger.info("Starting LiveKit worker...")
        import sys

        # Add parent directory to path so 'src' module can be imported
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

        sys.argv = ["calling_agent", "start"]

        from src.calling_agent import entrypoint
        from livekit.agents import WorkerOptions, cli

        cli.run_app(
            WorkerOptions(
                entrypoint_fnc=entrypoint,
                agent_name="intake-agent",
            )
        )
    except Exception as e:
        logger.error("LiveKit worker failed: %s", e, exc_info=True)
        raise


def main():
    """Run both health server and LiveKit worker using threading"""
    # Start health check server in a background thread
    health_thread = threading.Thread(
        target=run_health_server,
        name="HealthServer",
        daemon=True
    )
    health_thread.start()
    logger.info("Health server thread started")

    # Give the health server a moment to start
    import time
    time.sleep(2)

    # Run LiveKit worker in the main thread
    try:
        run_livekit_worker()
    except KeyboardInterrupt:
        logger.info("Shutting down worker...")


if __name__ == "__main__":
    main()
