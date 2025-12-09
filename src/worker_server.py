"""
Worker server that runs LiveKit agent with built-in HTTP health check.
Simplified version that leverages LiveKit's native HTTP server capabilities.
"""

import logging
import os

from livekit.agents import WorkerOptions, cli

logger = logging.getLogger("worker-server")
logging.basicConfig(level=logging.INFO)

def main():
    """Run LiveKit worker with built-in HTTP server for Cloud Run health checks"""
    try:
        logger.info("Starting LiveKit worker with HTTP health check...")

        # Import entrypoint and prewarm from calling_agent
        from src.calling_agent import entrypoint, prewarm
        import sys

        # Get port from environment (Cloud Run uses PORT env var)
        port = int(os.getenv("PORT", "8080"))

        # Configure WorkerOptions with HTTP server enabled
        worker_options = WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name="intake-agent",
            # Memory thresholds for Cloud Run
            job_memory_warn_mb=1024,    # Warn at 1GB
            job_memory_limit_mb=4096,   # Limit at 4GB
            initialize_process_timeout=5000,  # 5 second timeout
            prewarm_fnc=prewarm,
            # Enable HTTP server for health checks on Cloud Run port
            port=port,
        )

        logger.info(f"Starting worker on port {port}")
        # Add 'start' command to sys.argv for cli.run_app
        if len(sys.argv) == 1:
            sys.argv.append("start")
        cli.run_app(worker_options)

    except Exception as e:
        logger.error("LiveKit worker failed: %s", e, exc_info=True)
        raise


if __name__ == "__main__":
    main()
