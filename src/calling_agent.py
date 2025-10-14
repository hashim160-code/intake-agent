"""
ZScribe Intake Agent - AI-powered medical intake calls
"""

import logging
import os
import json
from dotenv import load_dotenv
from livekit.agents import JobContext, WorkerOptions, cli
from livekit.agents.voice import Agent
from livekit.agents import AgentSession, inference
from livekit.plugins import silero, deepgram, google
from src.prompts import generate_instructions_from_api, get_fallback_instructions
from datetime import datetime
import json
from livekit import api
load_dotenv()

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
    def __init__(self, template_id: str, organization_id: str, patient_id: str, 
                 appointment_details: dict) -> None:
        self.template_id = template_id
        self.organization_id = organization_id
        self.patient_id = patient_id
        self.appointment_details = appointment_details
        
        # Use fallback instructions initially
        instructions = get_fallback_instructions()
        
        super().__init__(
            instructions=instructions,
            stt=deepgram.STT(
                interim_results=True,
                endpointing_ms=500,          # KEY: Wait 500ms before finalizing transcript
                punctuate=True,
                smart_format=True
            ),
            llm=google.LLM(model="gemini-2.0-flash",),    # Google Gemini
            tts=deepgram.TTS(model="aura-asteria-en"),   # Deepgram TTS
            vad=_vad_model
        )

    async def on_enter(self):
        """Called when agent enters the room"""
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

        self.session.generate_reply()
        async def on_user_turn_completed(self, turn_ctx, new_message):
            """Log each user message"""
            logger.info(f"User: {new_message.text_content()}")


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

        incoming_details = parsed_metadata.get("appointment_details")
        if isinstance(incoming_details, dict):
            appointment_details = incoming_details
        elif incoming_details is not None:
            logger.warning("Appointment details must be a dict; ignoring value")

    logger.info(
        "Using - Template: %s, Org: %s, Patient: %s",
        template_id,
        organization_id,
        patient_id,
    )
    
    session = AgentSession()
    await session.start(
        agent=IntakeAgent(
            template_id=template_id,
            organization_id=organization_id,
            patient_id=patient_id,
            appointment_details=appointment_details,
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
            
            # Save conversation history
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(session.history.to_dict(), f, indent=2, ensure_ascii=False)
            
            logger.info(f"✅ Transcript saved: {filename}")
            
        except Exception as e:
            logger.error(f"❌ Failed to save transcript: {e}", exc_info=True)
    
    # Register the callback to run when session ends
    ctx.add_shutdown_callback(save_transcript)

if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name="intake-agent",
        )
    )

