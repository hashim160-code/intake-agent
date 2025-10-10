"""
ZScribe Intake Agent - AI-powered medical intake calls
"""

import logging
import json
from dotenv import load_dotenv
from livekit.agents import JobContext, WorkerOptions, cli
from livekit.agents.voice import Agent
from livekit.agents import AgentSession, inference
from livekit.plugins import silero, deepgram
from src.prompts import generate_instructions_from_api, get_fallback_instructions

load_dotenv()

logger = logging.getLogger("calling-agent")
logger.setLevel(logging.INFO)

# Pre-load VAD model to avoid timeout during job acceptance
_vad_model = silero.VAD.load()

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
            stt="assemblyai/universal-streaming",
            llm=inference.LLM(
                model="google/gemini-2.0-flash",
                extra_kwargs={
                    "max_completion_tokens": 800,
                    "temperature": 0.7
                }
            ),
            tts="cartesia/sonic-2:6f84f4b8-58a2-430c-8c79-688dad597532",
            vad=_vad_model  # Use pre-loaded VAD
        )

    async def on_enter(self):
        """Called when agent enters the room"""
        try:
            # Load dynamic instructions from API with all data
            logger.info(f"Loading data for template: {self.template_id}")
            logger.info(f"Organization ID: {self.organization_id}")
            logger.info(f"Patient ID: {self.patient_id}")
            logger.info(f"Appointment: {self.appointment_details.get('appointment_datetime', 'N/A')}")
            
            instructions = await generate_instructions_from_api(
                template_id=self.template_id,
                organization_id=self.organization_id,
                patient_id=self.patient_id,
                appointment_details=self.appointment_details
            )
            logger.info(f"Successfully loaded dynamic instructions")
            logger.info(f"Instructions preview: {instructions[:200]}...")
        except Exception as e:
            logger.error(f"Failed to load dynamic instructions: {e}")
            logger.error(f"Using fallback instructions instead")
    
        # Start the conversation
        self.session.generate_reply()

async def entrypoint(ctx: JobContext):
    """Main entrypoint for the agent"""
    
    # Initialize default values FIRST
    template_id = "bd9a2e9e-cdab-44d6-9882-58fc75ea9cda"
    organization_id = "0da4a59a-275f-4f2d-92f0-5e0c60b0f1da"
    patient_id = "4b3a1edb-76c5-46f4-ad0f-3c164348202b"
    appointment_details = {
        "appointment_datetime": "07/25/2025 06:38 PM",
        "provider_name": "Dr. Jane Smith"
    }
    
    # Check ctx.job for metadata
    logger.info(f"Job ID: {ctx.job.id}")
    logger.info(f"Job room name: {ctx.job.room.name}")
    
    # Try to access job.metadata (from dispatch)
    try:
        if hasattr(ctx.job, 'metadata') and ctx.job.metadata:
            metadata_str = ctx.job.metadata
            logger.info(f"Job metadata (raw): '{metadata_str}'")
            
            if metadata_str and metadata_str.strip():  # Check if not empty
                metadata = json.loads(metadata_str)
                template_id = metadata.get("template_id", template_id)
                organization_id = metadata.get("organization_id", organization_id)
                patient_id = metadata.get("patient_id", patient_id)
                appointment_details = metadata.get("appointment_details", appointment_details)
                logger.info(f"✅ Successfully parsed dispatch metadata")
            else:
                logger.info(f"ℹ️ Metadata is empty, using defaults")
        else:
            logger.info(f"ℹ️ No metadata attribute found, using defaults")
    except Exception as e:
        logger.error(f"Failed to parse metadata: {e}")
        logger.info(f"ℹ️ Using default values")
    
    logger.info(f"Using - Template: {template_id}, Org: {organization_id}, Patient: {patient_id}")
    
    session = AgentSession()
    
    await session.start(
        agent=IntakeAgent(
            template_id=template_id,
            organization_id=organization_id,
            patient_id=patient_id,
            appointment_details=appointment_details
        ),
        room=ctx.room
    )

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))