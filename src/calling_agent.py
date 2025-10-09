"""
---
title: Outbound Calling Agent
category: telephony
tags: [telephony, outbound-calls, survey, ice-cream-preference]
difficulty: beginner
description: Agent that makes outbound calls to ask about ice cream preferences
demonstrates:
  - Outbound call agent configuration
  - Goal-oriented conversation flow
  - Focused questioning strategy
  - Brief and direct interaction patterns
  - Automatic greeting generation
---
"""

import logging
import os
from pathlib import Path
from dotenv import load_dotenv
from livekit.agents import JobContext, WorkerOptions, cli
from livekit.agents.voice import Agent
from livekit.agents import AgentSession, inference
from livekit.plugins import silero, deepgram
from src.prompts import generate_template_specific_prompt  # Import the function
from src.tools import add_transcript_segment, save_transcript, get_transcript_summary

from src.state import StateManager, ConversationState, PatientInfo, TemplateInfo
load_dotenv()

logger = logging.getLogger("calling-agent")
logger.setLevel(logging.INFO)

class IntakeAgent(Agent):
    def __init__(self, template_name: str = "general_intake") -> None:  # Add template parameter
        # Generate dynamic instructions based on template
        instructions = generate_template_specific_prompt(template_name)
        
        super().__init__(
            instructions=instructions,  # Use dynamic instructions
            tools=[add_transcript_segment, save_transcript, get_transcript_summary],
            stt="assemblyai/universal-streaming",
            llm=inference.LLM(
                model="google/gemini-2.5-pro", # change model - 4.1, oss... 
                extra_kwargs={
                    "max_completion_tokens": 1000
                }
            ),
            tts="cartesia/sonic-2:6f84f4b8-58a2-430c-8c79-688dad597532",
            vad=silero.VAD.load() 
        )

    async def on_enter(self):
        self.session.generate_reply()
    
    
    
async def entrypoint(ctx: JobContext):
    session = AgentSession()

    # You can change the template here for testing
    template_name = "general_intake"  # or "cardiology_intake"
    
    await session.start(
        agent=IntakeAgent(template_name=template_name),  # Pass template name
        room=ctx.room
    )

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))