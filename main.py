"""
Main entry point for Cloud Run deployment
Runs both the intake API server and the LiveKit calling agent worker
"""

import logging
import multiprocessing
import os
import signal
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("main")


def run_intake_api():
    """Run the intake API server"""
    try:
        logger.info("Starting Intake API server...")
        from src.intake_api import main
        main()
    except Exception as e:
        logger.error("Failed to start Intake API: %s", e, exc_info=True)
        sys.exit(1)


def run_calling_agent():
    """Run the LiveKit calling agent worker"""
    try:
        logger.info("Starting LiveKit calling agent worker...")

        # Import here to avoid loading plugins in the main process
        import sys

        # Simulate running 'python src/calling_agent.py start'
        sys.argv = ['calling_agent', 'start']

        from src.calling_agent import entrypoint
        from livekit.agents import WorkerOptions, cli

        cli.run_app(
            WorkerOptions(
                entrypoint_fnc=entrypoint,
                agent_name="intake-agent",
            )
        )
    except Exception as e:
        logger.error("Failed to start calling agent: %s", e, exc_info=True)
        sys.exit(1)


def main():
    """
    Main function that starts both processes
    """
    logger.info("Starting ZScribe Intake Agent Service...")

    # Set multiprocessing start method for compatibility
    try:
        multiprocessing.set_start_method('spawn')
    except RuntimeError:
        # Already set
        pass

    # Start the calling agent worker in a separate process
    worker_process = multiprocessing.Process(
        target=run_calling_agent,
        name="CallingAgentWorker"
    )
    worker_process.start()
    logger.info("Calling agent worker started with PID: %d", worker_process.pid)

    # Handle shutdown gracefully
    def signal_handler(signum, frame):
        logger.info("Received signal %d, shutting down...", signum)
        if worker_process.is_alive():
            logger.info("Terminating worker process...")
            worker_process.terminate()
            worker_process.join(timeout=10)
            if worker_process.is_alive():
                logger.warning("Worker did not terminate, forcing kill...")
                worker_process.kill()
        sys.exit(0)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # Run the intake API in the main process
    # This blocks until the server is stopped
    try:
        run_intake_api()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        logger.info("Shutting down worker process...")
        if worker_process.is_alive():
            worker_process.terminate()
            worker_process.join(timeout=10)
            if worker_process.is_alive():
                worker_process.kill()


if __name__ == "__main__":
    main()
