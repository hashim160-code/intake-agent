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
from livekit.agents import AgentSession, inference
from livekit.plugins import silero, deepgram, noise_cancellation
from livekit.plugins.turn_detector.english import EnglishModel
from src.prompts import generate_instructions_from_api, get_fallback_instructions
from datetime import datetime
from livekit import api
from langfuse import Langfuse
from src.api_client import (
    save_transcript_to_db,
    fetch_patient_from_api,
    fetch_organization_from_api,
)

load_dotenv()
langfuse = Langfuse(
    secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
    host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
)

AGENT_NAME = os.getenv("INTAKE_AGENT_NAME", "ZScribe Intake Assistant")
DEFAULT_PATIENT_NAME = "there"
DEFAULT_ORGANIZATION_NAME = os.getenv("INTAKE_ORGANIZATION_NAME", "ZScribe")
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
    ) -> None:
        self.template_id = template_id
        self.organization_id = organization_id
        self.patient_id = patient_id
        self.patient_name = patient_name or DEFAULT_PATIENT_NAME
        self.organization_name = organization_name or DEFAULT_ORGANIZATION_NAME

        # Use fallback instructions initially
        instructions = get_fallback_instructions()

        super().__init__(
            instructions=instructions,
            stt=deepgram.STT(
                model="nova-3",
                language="en-US",
                smart_format=True,
            ),
            llm=inference.LLM(
                model="moonshotai/Kimi-K2-Instruct-0905",
                provider="baseten",
                extra_kwargs={
                    "max_tokens": 4000,
                    "temperature": 0.2,
                    "top_p": 0.5,
                },
            ),
            tts=deepgram.TTS(model="aura-2-thalia-en", mip_opt_out=True),
            vad=_vad_model,
        )

    async def on_enter(self):
        """Called when agent enters the room"""
        patient_name = self.patient_name
        organization_name = self.organization_name
        greeting_template = random.choice(GREETING_VARIATIONS)
        greeting = greeting_template.format(
            agent=AGENT_NAME, patient=patient_name, organization=organization_name
        )

        try:
            logger.info("Loading data for template %s", self.template_id)
            logger.info("Organization ID: %s", self.organization_id)
            logger.info("Patient ID: %s", self.patient_id)

            instructions = await generate_instructions_from_api(
                template_id=self.template_id,
                organization_id=self.organization_id,
                patient_id=self.patient_id,
                prefilled_greeting=greeting,
            )

            if instructions:
                await self.update_instructions(instructions)
                logger.info("Dynamic instructions applied")
                logger.info("Instructions preview: %s...", instructions[:200])
            else:
                logger.warning("Empty instructions returned; keeping fallback prompt")
        except Exception as e:
            logger.error("Failed to load dynamic instructions: %s", e, exc_info=True)
            logger.error("Using fallback instructions instead")

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

    # Safe fallback values so we can still run in dev/no-metadata scenarios
    template_id = os.getenv(
        "DEFAULT_TEMPLATE_ID", "bd9a2e9e-cdab-44d6-9882-58fc75ea9cda"
    )
    organization_id = os.getenv(
        "DEFAULT_ORGANIZATION_ID", "0da4a59a-275f-4f2d-92f0-5e0c60b0f1da"
    )
    patient_id = os.getenv(
        "DEFAULT_PATIENT_ID", "4b3a1edb-76c5-46f4-ad0f-3c164348202b"
    )
    intake_id = None

    logger.info("Job ID: %s", ctx.job.id)
    logger.info("Job room name: %s", ctx.job.room.name)

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
                    logger.info("Job metadata is an empty string; keeping defaults")
            elif isinstance(metadata_payload, dict):
                parsed_metadata = metadata_payload
            else:
                logger.warning(
                    "Unsupported metadata type %s; keeping defaults",
                    type(metadata_payload).__name__,
                )
        except Exception as e:
            logger.error("Failed to parse metadata: %s", e, exc_info=True)
        else:
            logger.info("Successfully parsed dispatch metadata")
    else:
        logger.warning("No metadata provided; continuing with default context")

    if parsed_metadata:
        template_id = parsed_metadata.get("template_id", template_id)
        organization_id = parsed_metadata.get("organization_id", organization_id)
        patient_id = parsed_metadata.get("patient_id", patient_id)
        intake_id = parsed_metadata.get("intake_id")

    patient_profile = None
    organization_profile = None
    try:
        patient_result, organization_result = await asyncio.gather(
            fetch_patient_from_api(patient_id),
            fetch_organization_from_api(organization_id),
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

    patient_name = (
        (patient_profile or {}).get("full_name")
        or DEFAULT_PATIENT_NAME
    )
    organization_name = (
        (organization_profile or {}).get("name")
        or DEFAULT_ORGANIZATION_NAME
    )
    if patient_name == DEFAULT_PATIENT_NAME:
        logger.info("Using default patient name; dynamic profile unavailable")
    if organization_name == DEFAULT_ORGANIZATION_NAME:
        logger.info("Using default organization name; dynamic profile unavailable")

    logger.info(
        "Using - Template: %s, Org: %s, Patient: %s",
        template_id,
        organization_id,
        patient_id,
    )

    # Start Langfuse span and set initial trace attributes
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

    span.update_trace(
        user_id=patient_id,
        session_id=ctx.room.name,
        input=call_input,
        metadata={
            "organization_id": organization_id,
            "template_id": template_id,
            "job_id": ctx.job.id,
            "call_started_at": datetime.now().isoformat()
        },
        tags=["production", "intake-agent"]
    )

    logger.info("Langfuse trace started for call session")

    # AgentSession with EnglishModel turn detection (matching voice/ agent)
    session = AgentSession(
        turn_detection=EnglishModel(),      # AI-powered turn detection
        min_interruption_words=2,           # Allow natural interruptions
        user_away_timeout=15,               # Handle silence (matching voice/ agent)
    )

    await session.start(
        agent=IntakeAgent(
            template_id=template_id,
            organization_id=organization_id,
            patient_id=patient_id,
            patient_name=patient_name,
            organization_name=organization_name,
        ),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVCTelephony()  # ✅ Noise cancellation for crystal clear audio!
        ),
    )

    # Save transcript when session ends
    async def save_transcript():
        try:
            # # Create transcripts folder if it doesn't exist
            # os.makedirs("transcripts", exist_ok=True)

            # # Create filename with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"transcripts/transcript_{ctx.room.name}_{timestamp}.json"

            # Get conversation history
            transcript_data = session.history.to_dict()

            # # Save conversation history to file
            # with open(filename, 'w', encoding='utf-8') as f:
            #     json.dump(transcript_data, f, indent=2, ensure_ascii=False)

            # logger.info("Transcript saved: %s", filename)

            if intake_id:
                try:
                    success = await save_transcript_to_db(intake_id, transcript_data)
                    if success:
                        logger.info("Transcript saved to database for intake: %s", intake_id)
                    else:
                        logger.error("Failed to save transcript to database for intake: %s", intake_id)
                except Exception as api_error:
                    logger.error("Error calling transcript API: %s", api_error, exc_info=True)
            else:
                logger.warning("No intake_id found in metadata, skipping database save")
                
            # Build a flattened transcript string for evaluations/quality checks
            transcript_items = transcript_data.get("items", [])
            plain_transcript_segments = []

            for item in transcript_items:
                role = (item.get("role") or "unknown").capitalize()
                content = item.get("content") or []

                if isinstance(content, str):
                    text = content
                elif isinstance(content, list):
                    # Join list entries (they are typically strings)
                    text = " ".join(str(part) for part in content if part)
                else:
                    text = ""

                if text:
                    plain_transcript_segments.append(f"{role}: {text.strip()}")

            transcript_text = "\n".join(plain_transcript_segments)

            # Update Langfuse trace with final data (v3.x API)
            span.update_trace(
                output=transcript_data,
                metadata={
                    "transcript_file": filename,
                    "message_count": len(transcript_data.get("items", [])),
                    "call_ended_at": datetime.now().isoformat(),
                    "transcript_text": transcript_text,
                }
            )

            logger.info("Langfuse trace updated with transcript data")

        except Exception as e:
            logger.error("Failed to save transcript or update trace: %s", e, exc_info=True)
        finally:
            # Always close out the Langfuse span even if transcript persistence fails
            try:
                span.end()
                langfuse.flush()
                logger.info("Langfuse span closed and data flushed")
            except Exception as span_error:
                logger.error("Failed to close Langfuse span cleanly: %s", span_error, exc_info=True)

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
