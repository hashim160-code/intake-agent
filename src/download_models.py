"""
Download models for LiveKit plugins during Docker build.
This script is called from Dockerfile.worker to pre-download all required models.
"""
import logging
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def download_all_models():
    """Explicitly download all required model files."""
    from livekit.plugins import silero

    logger.info("Downloading silero VAD model...")
    silero.VAD.load()
    logger.info("Silero VAD model downloaded!")

    # Try to download turn detector models
    try:
        from livekit.plugins.turn_detector.english import EnglishModel
        logger.info("Downloading turn detector models...")
        EnglishModel()
        logger.info("Turn detector models downloaded!")
    except Exception as e:
        logger.warning(f"Could not pre-download turn detector models: {e}")
        logger.warning("Models will be downloaded at runtime instead.")

    logger.info("Model download complete!")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "download-files":
        download_all_models()
    else:
        from livekit import agents
        agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=None))
