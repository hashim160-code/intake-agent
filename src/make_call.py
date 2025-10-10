import asyncio
import os
import logging
import json
from pathlib import Path
from dotenv import load_dotenv
from livekit import api

# Load environment variables
load_dotenv()

# Set up logging
logger = logging.getLogger("make-call")
logger.setLevel(logging.INFO)

# Configuration
room_name = "my-room"
agent_name = "test-agent"
outbound_trunk_id = os.getenv("SIP_OUTBOUND_TRUNK_ID")

async def make_call(phone_number: str, template_id: str, organization_id: str, 
                   patient_id: str, appointment_details: dict):
    """Create a dispatch and add a SIP participant to call the phone number"""
    lkapi = api.LiveKitAPI()
    
    # Create unique room name
    import uuid
    session_id = str(uuid.uuid4())[:8]
    room_name = f"intake-{session_id}"
    
    # Use agent_name to pass data (more professional)
    agent_name = "intake-agent"
    
    # Store data in metadata
    metadata = json.dumps({
        "template_id": template_id,
        "organization_id": organization_id,
        "patient_id": patient_id,
        "appointment_details": appointment_details,
        "phone_number": phone_number
    })
    
    logger.info(f"Creating dispatch with metadata: {metadata}")
    
    # Create agent dispatch with metadata
    dispatch = await lkapi.agent_dispatch.create_dispatch(
        api.CreateAgentDispatchRequest(
            agent_name=agent_name,
            room=room_name,
            metadata=metadata
        )
    )
    logger.info(f"Created dispatch: {dispatch}")
    
    # Create SIP participant to make the call
    if not outbound_trunk_id or not outbound_trunk_id.startswith("ST_"):
        logger.error("SIP_OUTBOUND_TRUNK_ID is not set or invalid")
        return
    
    logger.info(f"Dialing {phone_number} to room {room_name}")
    
    try:
        # Create SIP participant to initiate the call
        sip_participant = await lkapi.sip.create_sip_participant(
            api.CreateSIPParticipantRequest(
                room_name=room_name,  # Use the same unique room name
                sip_trunk_id=outbound_trunk_id,
                sip_call_to=phone_number,
                participant_identity="phone_user",
            )
        )
        logger.info(f"Created SIP participant: {sip_participant}")
    except Exception as e:
        logger.error(f"Error creating SIP participant: {e}")
    
    # Close API connection
    await lkapi.aclose()

async def main():
    # Appointment details (only appointment-specific data, no template/patient/org data) will discuss this whether it is required to go to agent or not with Ansaar bhaii
    appointment_details = {
        "appointment_id": "appt_123456789",
        "appointment_date": "07/25/2025",
        "appointment_time": "06:38 PM",
        "appointment_datetime": "07/25/2025 06:38 PM",
        "duration_minutes": 30,
        "appointment_type": "Initial Consultation",
        "status": "Scheduled",
        "provider_name": "Dr. Jane Smith",
        "location": "Main Clinic, Room 301",
        "notes": "Patient requires follow-up on previous lab results",
        "retries": 3,
        "timezone": "America/New_York"
    }
    
    # Test data
    phone_number = "+12146996918"
    template_id = "bd9a2e9e-cdab-44d6-9882-58fc75ea9cda"
    organization_id = "30f9486b-a049-45cd-ba2e-554d8ac06f92"
    patient_id = "4b3a1edb-76c5-46f4-ad0f-3c164348202b"
    
    await make_call(phone_number, template_id, organization_id, patient_id, appointment_details)

if __name__ == "__main__":
    asyncio.run(main())