import logging

from livekit import agents
from livekit.plugins import noise_cancellation, silero, turn_detector

logging.basicConfig(level=logging.INFO)


if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=None))
