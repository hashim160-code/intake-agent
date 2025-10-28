"""
ZScribe Intake Agent - AI-powered medical intake calls
"""

import logging
import os
import json
import random
from typing import Optional
from dotenv import load_dotenv
from livekit.agents import JobContext, WorkerOptions, cli
from livekit.agents.voice import Agent
from livekit.agents import AgentSession, inference
from livekit.plugins import silero, deepgram, baseten
from src.prompts import generate_instructions_from_api, get_fallback_instructions
from datetime import datetime
import json
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

logger = logging.getLogger("calling-agent")
logger.setLevel(logging.INFO)

# Pre-load VAD model to avoid timeout during job acceptance
_vad_model = silero.VAD.load()
# new one - tuned a little bit
# _vad_model = silero.VAD.load(
#     # min_speech_duration=0.05,        # Minimum duration to start detecting speech
#     min_silence_duration=0.1,        # KEY: Wait 0.1 second of silence before ending turn
#     # prefix_padding_duration=0.5,     # Add padding at start of speech
#     activation_threshold=0.35,        # Lower threshold = more sensitive (0.5 default)
#     # sample_rate=16000
# )

class IntakeAgent(Agent):
    def __init__(
        self,
        template_id: str,
        organization_id: str,
        patient_id: str,
        appointment_details: dict,
        patient_name: Optional[str] = None,
        organization_name: Optional[str] = None,
    ) -> None:
        self.template_id = template_id
        self.organization_id = organization_id
        self.patient_id = patient_id
        self.appointment_details = appointment_details
        self.patient_name = patient_name or DEFAULT_PATIENT_NAME
        self.organization_name = organization_name or DEFAULT_ORGANIZATION_NAME
        
        # Use fallback instructions initially
        instructions = get_fallback_instructions()
        
        super().__init__(
            instructions=instructions,
            stt=deepgram.STT(model="nova-3", language="en-US", smart_format=True),
            llm=inference.LLM(
                model="moonshotai/kimi-k2-instruct",
                provider="baseten",
                extra_kwargs={
                    "max_completion_tokens": 1000,
                    "temperature": 0.7,  # Adjust for natural conversation
                },
            ),
            tts=deepgram.TTS(model="aura-2-andromeda-en", mip_opt_out=True),
            vad=_vad_model
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
            logger.info(
                "Appointment: %s",
                self.appointment_details.get("appointment_datetime", "N/A"),
            )

            instructions = await generate_instructions_from_api(
                template_id=self.template_id,
                organization_id=self.organization_id,
                patient_id=self.patient_id,
                appointment_details=self.appointment_details,
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
        self.session.say(
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
    appointment_details: dict = {
        "appointment_datetime": "07/25/2025 06:38 PM",
        "provider_name": "Dr. Jane Smith",
    }
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

        incoming_details = parsed_metadata.get("appointment_details")
        if isinstance(incoming_details, dict):
            appointment_details = incoming_details
    elif incoming_details is not None:
        logger.warning("Appointment details must be a dict; ignoring value")

    patient_profile = None
    organization_profile = None
    try:
        patient_profile = await fetch_patient_from_api(patient_id)
    except Exception as exc:
        logger.warning("Unable to fetch patient data: %s", exc)
    try:
        organization_profile = await fetch_organization_from_api(organization_id)
    except Exception as exc:
        logger.warning("Unable to fetch organization data: %s", exc)

    patient_name = (
        (patient_profile or {}).get("full_name")
        or appointment_details.get("patient_name")
        or DEFAULT_PATIENT_NAME
    )
    organization_name = (
        (organization_profile or {}).get("name")
        or appointment_details.get("organization_name")
        or DEFAULT_ORGANIZATION_NAME
    )
    appointment_details.setdefault("patient_name", patient_name)
    appointment_details.setdefault("organization_name", organization_name)

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
        "appointment_details": appointment_details,
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
            "appointment_datetime": appointment_details.get("appointment_datetime"),
            "provider_name": appointment_details.get("provider_name"),
            "call_started_at": datetime.now().isoformat()
        },
        tags=["production", "intake-agent"]
    )

    logger.info("Langfuse trace started for call session")

    session = AgentSession()
    await session.start(
        agent=IntakeAgent(
            template_id=template_id,
            organization_id=organization_id,
            patient_id=patient_id,
            appointment_details=appointment_details,
            patient_name=patient_name,
            organization_name=organization_name,
        ),
        room=ctx.room,
    )

    # Save transcript when session ends
    async def save_transcript():
        try:
            # Create transcripts folder if it doesn't exist
            os.makedirs("transcripts", exist_ok=True)

            # Create filename with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"transcripts/transcript_{ctx.room.name}_{timestamp}.json"

            # Get conversation history
            transcript_data = session.history.to_dict()

            # Save conversation history to file
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(transcript_data, f, indent=2, ensure_ascii=False)

            logger.info("Transcript saved: %s", filename)

            # Save to database via API
            if intake_id:
                try:
                    success = await save_transcript_to_db(intake_id, transcript_data)
                    if success:
                        logger.info("✅ Transcript saved to database for intake: %s", intake_id)
                    else:
                        logger.error("❌ Failed to save transcript to database for intake: %s", intake_id)
                except Exception as api_error:
                    logger.error("❌ Error calling transcript API: %s", api_error, exc_info=True)
            else:
                logger.warning("⚠️ No intake_id found in metadata, skipping database save")
                
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
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name="intake-agent",
        )
    )

