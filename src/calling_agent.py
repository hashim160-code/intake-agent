"""
ZScribe Intake Agent - AI-powered medical intake calls
"""

# ------------------------------------------------------------------ #
# Logging Configuration - MUST BE FIRST!
# ------------------------------------------------------------------ #
from __future__ import annotations

import logging

# Configure logging immediately before any other imports
logging.getLogger().handlers.clear()
logging.basicConfig(
    level=logging.ERROR,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    force=True,
)

# Aggressively suppress external libraries BEFORE they get imported
logging.getLogger("httpx").setLevel(logging.CRITICAL)
logging.getLogger("httpcore").setLevel(logging.CRITICAL)
logging.getLogger("httpcore.http11").setLevel(logging.CRITICAL)
logging.getLogger("httpcore.connection").setLevel(logging.CRITICAL)
logging.getLogger("deepgram").setLevel(logging.CRITICAL)
logging.getLogger("openai").setLevel(logging.CRITICAL)
logging.getLogger("openai._base_client").setLevel(logging.CRITICAL)
logging.getLogger("azure").setLevel(logging.CRITICAL)
logging.getLogger("azure.core").setLevel(logging.CRITICAL)
logging.getLogger("urllib3").setLevel(logging.CRITICAL)
logging.getLogger("langsmith").setLevel(logging.CRITICAL)
logging.getLogger("langsmith.client").setLevel(logging.CRITICAL)
logging.getLogger("langchain").setLevel(logging.ERROR)
logging.getLogger("langgraph").setLevel(logging.ERROR)
logging.getLogger("livekit").setLevel(logging.INFO)
# Suppress LiveKit memory warnings specifically (they're too conservative for AI apps)
logging.getLogger("livekit.agents").setLevel(logging.INFO)

# ------------------------------------------------------------------ #
# Imports and Environment Setup
# ------------------------------------------------------------------ #

import os
import json
from typing import Optional
import random
import asyncio
from dotenv import load_dotenv
from livekit.agents import JobContext, WorkerOptions, cli, RoomInputOptions, JobProcess
from livekit.agents.voice import Agent
from livekit.agents import AgentSession
from livekit.plugins import silero, deepgram, noise_cancellation, groq
from livekit.plugins.turn_detector.english import EnglishModel
from src.prompts import generate_instructions_from_api, get_fallback_instructions
from datetime import datetime
from livekit import api
from langfuse import Langfuse
from src.db_utils import (
    save_transcript as save_transcript_to_db,
    fetch_patient,
    fetch_organization,
)

load_dotenv()

# Setup logger first
logger = logging.getLogger(__name__)

# Initialize Langfuse with error handling
langfuse = None
try:
    langfuse_secret = os.getenv("LANGFUSE_SECRET_KEY")
    langfuse_public = os.getenv("LANGFUSE_PUBLIC_KEY")
    langfuse_host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

    if langfuse_secret and langfuse_public:
        langfuse = Langfuse(
            secret_key=langfuse_secret,
            public_key=langfuse_public,
            host=langfuse_host
        )
        logger.info("Langfuse initialized successfully")
    else:
        logger.warning("Langfuse credentials not found - tracing will be disabled")
except Exception as e:
    logger.error("Failed to initialize Langfuse: %s - tracing will be disabled", e, exc_info=True)
    langfuse = None

# Constants
AGENT_NAME = "ZScribe Intake Coordinator"
DEFAULT_PATIENT_NAME = "there"
DEFAULT_ORGANIZATION_NAME = "our office"
GREETING_VARIATIONS = [
    "Hello {patient}, this is {agent} calling from {organization}. Is this a good time to talk for a few minutes?",
    "Hi {patient}, {agent} from {organization}. Do you have a moment so we can prepare for your upcoming appointment?",
    "Good day {patient}! You're speaking with {agent} at {organization}. May I confirm it's a convenient time to go through a few intake questions?",
    "Hello {patient}, you're speaking with {agent} representing {organization}. Is it okay if we continue with your intake call now?",
]

# Setup logger
logger = logging.getLogger(__name__)

# Pre-load VAD model - using defaults like voice/ agent
_vad_model = silero.VAD.load()


def prewarm(proc: JobProcess):
    """Prewarm function to load VAD and TTS models before job acceptance"""
    proc.userdata["vad"] = silero.VAD.load()  # Using defaults like voice/ agent
    proc.userdata["tts"] = deepgram.TTS(model="aura-2-thalia-en", mip_opt_out=True)


class IntakeAgent(Agent):
    def __init__(
        self,
        template_id: str,
        organization_id: str,
        patient_id: str,
        patient_name: Optional[str] = None,
        organization_name: Optional[str] = None,
        agent_name: Optional[str] = None,
        instructions: Optional[str] = None,
    ) -> None:
        self.template_id = template_id
        self.organization_id = organization_id
        self.patient_id = patient_id
        self.patient_name = patient_name or DEFAULT_PATIENT_NAME
        self.organization_name = organization_name or DEFAULT_ORGANIZATION_NAME
        self.agent_name = agent_name or AGENT_NAME

        # Use provided instructions or fallback
        final_instructions = instructions if instructions else get_fallback_instructions()

        super().__init__(
            instructions=final_instructions,
            stt=deepgram.STT(
                model="nova-3",
                language="en-US",
                smart_format=True,
            ),
            llm=groq.LLM(
                model="moonshotai/kimi-k2-instruct-0905",
                temperature=0.2,
            ),
            tts=deepgram.TTS(model="aura-2-thalia-en", mip_opt_out=True),
            vad=_vad_model,
        )

    async def on_enter(self):
        """Called when agent enters the room - Stage 2"""
        patient_name = self.patient_name
        organization_name = self.organization_name
        agent_name = self.agent_name

        # Generate greeting
        greeting_template = random.choice(GREETING_VARIATIONS)
        greeting = greeting_template.format(
            agent=agent_name, patient=patient_name, organization=organization_name
        )

        logger.info("Agent entering room - Template: %s, Org: %s, Patient: %s",
                   self.template_id, self.organization_id, self.patient_id)

        # Small delay to ensure audio stream is ready before speaking
        await asyncio.sleep(0.5)

        await self.session.say(
            greeting,
            allow_interruptions=True,
            add_to_chat_ctx=True,
        )

    async def on_user_turn_completed(self, turn_ctx, new_message):
        """Log each user message"""
        message_text = getattr(new_message, "text_content", None)
        if callable(message_text):
            message_text = message_text()
        elif message_text is None:
            message_text = getattr(new_message, "text", None)
            if callable(message_text):
                message_text = message_text()

        if message_text is None:
            message_text = str(new_message)

        logger.info("User: %s", message_text)


async def entrypoint(ctx: JobContext):
    """Main entrypoint for the agent"""

    logger.info("Job ID: %s", ctx.job.id)
    logger.info("Job room name: %s", ctx.job.room.name)

    # Initialize variables - will be populated from metadata
    template_id = None
    organization_id = None
    patient_id = None
    intake_id = None

    metadata_payload = getattr(ctx.job, "metadata", None)
    parsed_metadata = None

    if metadata_payload:
        try:
            if isinstance(metadata_payload, bytes):
                metadata_payload = metadata_payload.decode("utf-8")

            if isinstance(metadata_payload, str):
                metadata_payload = metadata_payload.strip()
                if metadata_payload:
                    parsed_metadata = json.loads(metadata_payload)
                else:
                    logger.warning("Job metadata is empty string")
            elif isinstance(metadata_payload, dict):
                parsed_metadata = metadata_payload
            else:
                logger.warning(
                    "Unsupported metadata type %s",
                    type(metadata_payload).__name__,
                )
        except Exception as e:
            logger.error("Failed to parse metadata: %s", e, exc_info=True)
        else:
            logger.info("Successfully parsed dispatch metadata")
    else:
        logger.warning("No metadata provided")

    # Extract IDs from parsed metadata
    if parsed_metadata:
        template_id = parsed_metadata.get("template_id")
        organization_id = parsed_metadata.get("organization_id")
        patient_id = parsed_metadata.get("patient_id")
        intake_id = parsed_metadata.get("intake_id")

    # Validate required fields
    if not template_id or not organization_id or not patient_id:
        error_msg = f"Missing required metadata - template_id: {template_id}, organization_id: {organization_id}, patient_id: {patient_id}"
        logger.error(error_msg)
        raise ValueError(error_msg)

    patient_profile = None
    organization_profile = None
    try:
        patient_result, organization_result = await asyncio.gather(
            fetch_patient(patient_id),
            fetch_organization(organization_id),
            return_exceptions=True,
        )
    except Exception as exc:
        logger.warning("Parallel metadata fetch failed: %s", exc)
        patient_result = organization_result = None

    if isinstance(patient_result, Exception):
        logger.warning("Unable to fetch patient data: %s", patient_result)
        patient_profile = None
    else:
        patient_profile = patient_result

    if isinstance(organization_result, Exception):
        logger.warning("Unable to fetch organization data: %s", organization_result)
        organization_profile = None
    else:
        organization_profile = organization_result

    # Extract names with fallback to defaults
    if patient_profile and patient_profile.get("full_name"):
        patient_name = patient_profile.get("full_name")
    else:
        patient_name = DEFAULT_PATIENT_NAME
        logger.info("Using default patient name; dynamic profile unavailable")

    if organization_profile and organization_profile.get("name"):
        organization_name = organization_profile.get("name")
    else:
        organization_name = DEFAULT_ORGANIZATION_NAME
        logger.info("Using default organization name; dynamic profile unavailable")

    logger.info(
        "Using - Template: %s, Org: %s, Patient: %s",
        template_id,
        organization_id,
        patient_id,
    )

    # STAGE 1: Fetch template instructions during dispatch (before room entry)
    logger.info("Stage 1 (Dispatch): Fetching template instructions")
    instructions = None
    try:
        # Generate a temporary greeting for instructions compilation
        greeting_template = random.choice(GREETING_VARIATIONS)
        temp_greeting = greeting_template.format(
            agent=AGENT_NAME,
            patient=patient_name,
            organization=organization_name
        )

        instructions = await generate_instructions_from_api(
            template_id=template_id,
            organization_id=organization_id,
            patient_id=patient_id,
            prefilled_greeting=temp_greeting,
        )

        if instructions:
            logger.info("Template instructions fetched successfully during dispatch")
            logger.info("Instructions preview: %s...", instructions[:200])
        else:
            logger.warning("Empty instructions returned; will use fallback")
    except Exception as e:
        logger.error("Failed to fetch template instructions during dispatch: %s", e, exc_info=True)
        logger.warning("Will use fallback instructions")

    # Start Langfuse span and set initial trace attributes (with null check)
    span = None
    if langfuse:
        try:
            span = langfuse.start_span(name="intake-call")

            # Set input data - the parameters that initiated this call
            call_input = {
                "organization_id": organization_id,
                "template_id": template_id,
                "patient_id": patient_id,
                "organization_name": organization_name,
                "patient_name": patient_name,
                "job_id": ctx.job.id,
                "room_name": ctx.room.name
            }

            # Get environment from env variable (development, staging, production)
            environment = os.getenv("ENVIRONMENT", "development")

            span.update_trace(
                user_id=patient_id,
                session_id=ctx.room.name,
                input=call_input,
                metadata={
                    "organization_id": organization_id,
                    "template_id": template_id,
                    "job_id": ctx.job.id,
                    "call_started_at": datetime.now().isoformat(),
                    "environment": environment
                },
                tags=[environment, "intake-agent"]
            )

            logger.info("Langfuse trace started for call session")
        except Exception as e:
            logger.warning("Failed to start Langfuse trace: %s", e)
            span = None
    else:
        logger.debug("Langfuse not available - skipping tracing")

    # AgentSession with turn detection (models now embedded in Docker image)
    session = AgentSession(
        turn_detection=EnglishModel(),      # Re-enabled: model files embedded in Docker image
        min_interruption_words=2,           # Allow natural interruptions
        user_away_timeout=15,               # Handle silence (matching voice/ agent)
    )

    # STAGE 2: Start session with pre-fetched instructions
    logger.info("Stage 2: Starting agent session with room entry")
    await session.start(
        agent=IntakeAgent(
            template_id=template_id,
            organization_id=organization_id,
            patient_id=patient_id,
            patient_name=patient_name,
            organization_name=organization_name,
            instructions=instructions,  # Pass pre-fetched instructions from Stage 1
        ),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVCTelephony()  # ✅ Noise cancellation for crystal clear audio!
        ),
    )

    # STAGE 3: Save transcript when session ends (cleanup/disconnect)
    async def save_transcript():
        """Stage 3 - Called on room disconnect for cleanup tasks"""
        logger.info("Stage 3 (Cleanup): Saving transcript and flushing observability data")
        try:
            # Get conversation history
            transcript_data = session.history.to_dict()

            # Save to database
            if intake_id:
                try:
                    success = await save_transcript_to_db(intake_id, transcript_data)
                    if success:
                        logger.info("Transcript saved to database for intake: %s", intake_id)
                    else:
                        logger.error("Failed to save transcript to database for intake: %s", intake_id)
                except Exception as db_error:
                    logger.error("Error saving transcript to database: %s", db_error, exc_info=True)
            else:
                logger.warning("No intake_id found in metadata, skipping database save")

            # Build a flattened transcript string for Langfuse trace
            transcript_items = transcript_data.get("items", [])
            plain_transcript_segments = []

            for item in transcript_items:
                role = (item.get("role") or "unknown").capitalize()
                content = item.get("content") or []

                if isinstance(content, str):
                    text = content
                elif isinstance(content, list):
                    text = " ".join(str(part) for part in content if part)
                else:
                    text = ""

                if text:
                    plain_transcript_segments.append(f"{role}: {text.strip()}")

            transcript_text = "\n".join(plain_transcript_segments)

            # Update Langfuse trace with final data
            if span and langfuse:
                try:
                    span.update_trace(
                        output=transcript_data,
                        metadata={
                            "message_count": len(transcript_data.get("items", [])),
                            "call_ended_at": datetime.now().isoformat(),
                            "transcript_text": transcript_text,
                        }
                    )
                    logger.info("Langfuse trace updated with transcript data")
                except Exception as trace_error:
                    logger.warning("Failed to update Langfuse trace: %s", trace_error)

        except Exception as e:
            logger.error("Failed to save transcript or update trace: %s", e, exc_info=True)
        finally:
            # Always close out the Langfuse span even if transcript persistence fails
            if span and langfuse:
                try:
                    span.end()
                    langfuse.flush()
                    logger.info("Langfuse span closed and data flushed")
                except Exception as span_error:
                    logger.warning("Failed to close Langfuse span cleanly: %s", span_error)

    # Register the callback to run when session ends
    ctx.add_shutdown_callback(save_transcript)

if __name__ == "__main__":
    # Configure WorkerOptions with higher memory thresholds
    worker_options = WorkerOptions(
        entrypoint_fnc=entrypoint,
        agent_name="intake-agent",
        # Increase memory warning threshold to 1GB (1024MB) to avoid false warnings
        # Default is 500MB which is too low for complex AI applications
        job_memory_warn_mb=1024,  # Warn at 1GB instead of 500MB
        job_memory_limit_mb=4096,  # Set limit at 4GB for safety
        initialize_process_timeout=5000,  # 5 second timeout for process initialization
        prewarm_fnc=prewarm,
    )
    cli.run_app(worker_options)
