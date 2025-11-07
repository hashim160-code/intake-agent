"""
Worker service entrypoint for Cloud Run.

Cloud Run requires every container to bind to the HTTP port exposed via the
`PORT` environment variable. The LiveKit worker started by
`livekit.agents.cli.run_app` does not expose such an endpoint, so we launch it
in a background thread and keep a lightweight FastAPI app running to satisfy
the health probes.
"""

import os
import threading

from fastapi import FastAPI
import uvicorn
from livekit.agents import WorkerOptions, cli

from src.calling_agent import entrypoint


def _start_worker() -> None:
    """Launch the LiveKit worker (blocking call)."""
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name=os.getenv("INTAKE_AGENT_NAME", "intake-agent"),
        )
    )


def create_health_app() -> FastAPI:
    """FastAPI app that exposes a simple health endpoint."""
    app = FastAPI(title="Intake Agent Worker Health", version="1.0.0")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


def main() -> None:
    worker_thread = threading.Thread(target=_start_worker, name="livekit-worker", daemon=True)
    worker_thread.start()

    app = create_health_app()
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
