"""
ZScribe Intake Agent - AI-powered medical intake calls
"""

import logging
from dotenv import load_dotenv
from livekit.agents import JobContext, WorkerOptions, cli
from livekit.agents.voice import Agent
from livekit.agents import AgentSession, inference
from livekit.plugins import silero, deepgram
from src.prompts import generate_instructions_from_api, get_fallback_instructions

load_dotenv()

logger = logging.getLogger("calling-agent")
logger.setLevel(logging.INFO)

class IntakeAgent(Agent):
    def __init__(self, template_id: str = "bd9a2e9e-cdab-44d6-9882-58fc75ea9cda") -> None:
        self.template_id = template_id
        
        # Use fallback instructions initially
        instructions = get_fallback_instructions()
        
        super().__init__(
            instructions=instructions,
            stt="assemblyai/universal-streaming",
            llm=inference.LLM(
                model="google/gemini-2.0-flash", 
                extra_kwargs={
                    "max_completion_tokens": 1000
                }
            ),
            tts="cartesia/sonic-2:6f84f4b8-58a2-430c-8c79-688dad597532",
            vad=silero.VAD.load() 
        )

    async def on_enter(self):
        """Called when agent enters the room"""
        try:
            # Load dynamic instructions from API
            logger.info(f"Attempting to fetch template:{self.template_id}")
            instructions = await generate_instructions_from_api(self.template_id)
            logger.info(f"Successfully loaded template instructions")
            logger.info(f"Instructions preview: {instructions[:200]}...")
        except Exception as e:
            logger.error(f"Failed to load template instructions: {e}")
            logger.error(f"Using fallback instructions instead")
    
        # Start the conversation
        self.session.generate_reply()

async def entrypoint(ctx: JobContext):
    """Main entrypoint for the agent"""
    session = AgentSession()
    
    # Template ID from your database
    template_id = "bd9a2e9e-cdab-44d6-9882-58fc75ea9cda"
    
    await session.start(
        agent=IntakeAgent(template_id=template_id),
        room=ctx.room
    )

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))