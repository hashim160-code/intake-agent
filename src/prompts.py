"""
Template-based prompt generation for intake agent
"""

import os
import logging
from typing import Optional
from langfuse import Langfuse
from src.api_client import fetch_template_from_api, fetch_patient_from_api, fetch_organization_from_api

logger = logging.getLogger("calling-agent")

# Initialize Langfuse client for prompt fetching
langfuse_client = Langfuse(
    secret_key=os.getenv("INTAKE_LANGFUSE_SECRET_KEY") or os.getenv("LANGFUSE_SECRET_KEY"),
    public_key=os.getenv("INTAKE_LANGFUSE_PUBLIC_KEY") or os.getenv("LANGFUSE_PUBLIC_KEY"),
    host=os.getenv("INTAKE_LANGFUSE_HOST") or os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
)

async def generate_instructions_from_api(
    template_id: str,
    organization_id: str | None = None,
    patient_id: str | None = None,
    prefilled_greeting: Optional[str] = None,
) -> str:
    """Generate complete instructions from Langfuse prompt template with API data"""

    def append_greeting_note(text: str) -> str:
        if not prefilled_greeting:
            return text
        return (
            f"{text}\n\nNOTE: The assistant has already greeted the patient by saying "
            f"\"{prefilled_greeting}\" and has already asked if it's a good time to talk. "
            "Do NOT repeat the introduction or permission question unless the patient indicates they didn't hear it. "
            "Wait for the patient's reply to that greeting before continuing with the intake flow."
        )

    # Fetch all data in parallel
    template_data = await fetch_template_from_api(template_id)
    patient_data = await fetch_patient_from_api(patient_id) if patient_id else None
    organization_data = await fetch_organization_from_api(organization_id) if organization_id else None

    if not template_data:
        logger.warning("Template data not available, using fallback instructions")
        return append_greeting_note(get_fallback_instructions())

    # Extract the data
    template_name = template_data.get('template_name', 'Intake Form')
    instructions_for_ai = template_data.get('instructions_for_ai', 'Follow standard medical intake protocol.')
    questions = template_data.get('questions', [])

    patient_name = patient_data.get('full_name', 'the patient') if patient_data else 'the patient'
    organization_name = organization_data.get('name', 'your medical office') if organization_data else 'your medical office'

    # Format questions list
    questions_list = ""
    for i, question in enumerate(questions, 1):
        question_text = question.get('text', 'Question not available')
        questions_list += f"{i}. {question_text}\n"

    # Fetch prompt from Langfuse
    try:
        prompt = langfuse_client.get_prompt("intake-agent-instructions", label="production")

        # Compile prompt with variables
        instructions = prompt.compile(
            patient_name=patient_name,
            organization_name=organization_name,
            template_name=template_name,
            instructions_for_ai=instructions_for_ai,
            questions_list=questions_list.strip()
        )

        logger.info("Successfully fetched and compiled prompt from Langfuse")
        return append_greeting_note(instructions)

    except Exception as e:
        logger.error(f"Failed to fetch prompt from Langfuse: {e}, using fallback")
        return append_greeting_note(get_fallback_instructions())

def get_fallback_instructions() -> str:
    """Get fallback instructions when Langfuse or API is not available"""
    return """You are a medical intake agent. Collect patient information professionally.

Start with a greeting, ask if it's a good time to talk, then ask about:
1. Chief complaint
2. Symptoms
3. Medical history
4. Medications
5. Allergies

Ask questions one by one and be conversational."""
